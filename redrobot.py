import blenderproc as bproc
import os
import numpy as np
from pathlib import Path
import bpy

#Define paths
bop_parent_path = "Data" # parent folder of dataset
cc_textures_path = "cc_textures" # folder containing cc_textures
output_dir="output" # output directory
texture = Path("Data/RedRobot/models/baked_mesh_tex0.png") # load texture for husky

bproc.init()

# load bop objects into the scene
target_bop_objs = bproc.loader.load_bop_objs(bop_dataset_path = os.path.join(bop_parent_path, 'RedRobot'), mm2m = True)

for obj in target_bop_objs:
    obj.set_scale([1 ,1,1])


# load BOP datset intrinsics
bproc.loader.load_bop_intrinsics(bop_dataset_path = os.path.join(bop_parent_path, 'RedRobot'))

for obj in (target_bop_objs):
    obj.set_shading_mode('auto')
    obj.hide(True)
    
# create room
room_planes = [bproc.object.create_primitive('PLANE', scale=[4, 4, 1]),
               bproc.object.create_primitive('PLANE', scale=[4, 4, 1], location=[0, -4, 4], rotation=[-1.570796, 0, 0]),
               bproc.object.create_primitive('PLANE', scale=[4, 4, 1], location=[0, 4, 4], rotation=[1.570796, 0, 0]),
               bproc.object.create_primitive('PLANE', scale=[4, 4, 1], location=[4, 0, 4], rotation=[0, -1.570796, 0]),
               bproc.object.create_primitive('PLANE', scale=[4, 4, 1], location=[-4, 0, 4], rotation=[0, 1.570796, 0])]

# sample light color and strenght from ceiling
light_plane = bproc.object.create_primitive('PLANE', scale=[3, 3, 1], location=[0, 0, 10])
light_plane.set_name('light_plane')
light_plane_material = bproc.material.create('light_material')

# sample point light on shell
light_point = bproc.types.Light()
light_point.set_energy(200)

# load cc_textures
cc_textures = bproc.loader.load_ccmaterials(cc_textures_path)

# Define a function that samples 6-DoF poses
def sample_pose_func(obj: bproc.types.MeshObject):
    min = np.random.uniform([-0.3, -0.3, 0.0], [-0.2, -0.2, 0.0])
    max = np.random.uniform([0.2, 0.2, 0.4], [0.3, 0.3, 0.6])
    obj.set_location(np.random.uniform(min, max))
    
# activate depth rendering without antialiasing and set amount of samples for color rendering
bproc.renderer.enable_depth_output(activate_antialiasing=False)
bproc.renderer.set_max_amount_of_samples(50)





sampled_target_bop_objs = list(target_bop_objs)

for obj in (sampled_target_bop_objs):
    mat = obj.get_materials()[0]  
    if obj.get_cp("bop_dataset_name") in ["RedRobot"]:
        image = bpy.data.images.load(filepath=str(texture))
        mat.set_principled_shader_value("Base Color",image)    
    mat.set_principled_shader_value("Roughness", np.random.uniform(0, 1.0))
    obj.hide(False)

# Sample two light sources
light_plane_material.make_emissive(emission_strength=np.random.uniform(3,6), 
                                emission_color=np.random.uniform([0.5, 0.5, 0.5, 1.0], [1.0, 1.0, 1.0, 1.0]))  
light_plane.replace_materials(light_plane_material)
light_point.set_color(np.random.uniform([0.5,0.5,0.5],[1,1,1]))
location = bproc.sampler.shell(center = [0, 0, 0], radius_min = 1, radius_max = 1.5,
                        elevation_min = 5, elevation_max = 89)
light_point.set_location(location)

# sample CC Texture and assign to room planes
random_cc_texture = np.random.choice(cc_textures)
for plane in room_planes:
    plane.replace_materials(random_cc_texture)


# Sample object poses and check collisions 
bproc.object.sample_poses(objects_to_sample = sampled_target_bop_objs ,sample_pose_func = sample_pose_func, max_tries = 1000)
        
# Define a function that samples the initial pose of a given object above the ground
def sample_initial_pose(obj: bproc.types.MeshObject):
    obj.set_location(bproc.sampler.upper_region(objects_to_sample_on=room_planes[0:1],
                                                min_height=1, max_height=4, face_sample_range=[0.4, 0.6]))
    obj.set_rotation_euler(np.random.uniform([0, 0, 0], [0, 0, np.pi * 2]))

# Sample objects on the given surface
placed_objects = bproc.object.sample_poses_on_surface(objects_to_sample=sampled_target_bop_objs,
                                                        surface=room_planes[0],
                                                        sample_pose_func=sample_initial_pose,
                                                        min_distance=0.01,
                                                        max_distance=0.2)

# BVH tree used for camera obstacle checks
bop_bvh_tree = bproc.object.create_bvh_tree_multi_objects(sampled_target_bop_objs)

cam_poses = 0
while cam_poses < 25:
    # Sample location
    location = bproc.sampler.shell(center = [0, 0, 0],
                            radius_min = 1,
                            radius_max = 3.5,
                            elevation_min = 10,
                            elevation_max = 89)
    # Determine point of interest in scene as the object closest to the mean of a subset of objects
    poi = bproc.object.compute_poi(sampled_target_bop_objs)
    # Compute rotation based on vector going from location towards poi
    rotation_matrix = bproc.camera.rotation_from_forward_vec(poi - location, inplane_rot=np.random.uniform(-0.7854, 0.7854))
    # Add homog cam pose based on location an rotation
    cam2world_matrix = bproc.math.build_transformation_mat(location, rotation_matrix)
    
    # Check that obstacles are at least 0.3 meter away from the camera and make sure the view interesting enough
    if bproc.camera.perform_obstacle_in_view_check(cam2world_matrix, {"min": 0.5}, bop_bvh_tree):
        # Persist camera pose
        bproc.camera.add_camera_pose(cam2world_matrix, frame=cam_poses)
        cam_poses += 1

# render the whole pipeline
data = bproc.renderer.render()

# Write data in bop format
bproc.writer.write_bop(os.path.join(output_dir, 'bop_data'),
                        target_objects = sampled_target_bop_objs,
                        dataset = 'RedRobot',
                        depth_scale = 1,
                        depths = data["depth"],
                        colors = data["colors"], 
                        color_file_format = "JPEG",
                        ignore_dist_thres = 10)   
for obj in (sampled_target_bop_objs):      
    obj.hide(True)
