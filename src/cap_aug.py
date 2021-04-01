# coding: utf-8
__author__ = 'RocketFlash: https://github.com/RocketFlash'

import cv2
import numpy as np
import random
from skimage import exposure

def resize_keep_ar(image, height=500):
    r = height / float(image.shape[0])
    width = r * image.shape[1]  
    image = cv2.resize(image, (int(width), int(height)))
    return image


class CAP_AUG_Multiclass(object):
    '''
    cap_augs - list of cap augmentations for each class
    probabilities - list of probabilities fro each augmentation
    class_idxs - class indexes 
    '''
    def __init__(self, cap_augs, probabilities, class_idxs):
        self.cap_augs = cap_augs
        self.probabilities = probabilities
        self.class_idxs = class_idxs
        assert len(self.cap_augs)==len(self.probabilities) and \
               len(self.cap_augs)==len(self.class_idxs)


    def __call__(self, image):
        return self.generate_objects(image)


    def generate_objects(self, image):
        result_image = image.copy()
        total_result_coords = []
        total_semantic_masks = []
        total_instance_masks = []

        for cap_aug, p, class_idx in zip(self.cap_augs, self.probabilities, self.class_idxs):
            if p>=np.random.uniform(0, 1, size=1):
                result_image, result_coords, semantic_mask, instance_mask = cap_aug(result_image)
                total_result_coords.append(np.c_[class_idx*np.ones(len(result_coords)), result_coords])
                total_semantic_masks.append(semantic_mask)
                total_instance_masks.append(instance_mask)
                
        if len(total_result_coords)>0:
            total_result_coords = np.vstack(total_result_coords)

        result_sem_mask = None

        for sem_mask, class_idx in zip(total_semantic_masks, self.class_idxs):
            if result_sem_mask is None:
                result_sem_mask = sem_mask * class_idx
            else:
                result_sem_mask[sem_mask==1] = class_idx
        
        return result_image, total_result_coords, result_sem_mask, total_instance_masks
    

class CAP_AUG(object):
    '''
    source_images - list of images paths
    bev_transform - bird's eye view transformation
    probability_map - mask with brobability values
    mean_h_norm - mean normilized heiht
    n_objects_range - [min, max] number of objects
    h_range - range of objects heights
              if bev_transform is not None range in meters, else in pixels
    x_range - if bev_transform is None -> range in the image coordinate system (in pixels) [int, int]
              else                     -> range in camera coordinate system (in meters) [float, float]
    y_range - if bev_transform is None -> range in the image coordinate system (in pixels) [int, int]
              else                     -> range in camera coordinate system (in meters) [float, float]
    z_range - if bev_transform is None -> range in the image coordinate system (in pixels) [int, int]
              else                     -> range in camera coordinate system (in meters) [float, float]
    objects_idxs - objects indexes from dataset to paste [idx1, idx2, ...]
    random_h_flip - source image random horizontal flip
    random_v_flip - source image random vertical flip
    histogram_matching - apply histogram matching
    hm_offset - histogram matching offset
    blending_coeff - coefficient of image blending
    image_format - color image format : {bgr, rgb}
    coords_format - output coordinates format: {xyxy, xywh, yolo}
    normilized_range - range in normilized image coordinates (all values are in range [0, 1])  
    '''
    def __init__(self, source_images, bev_transform=None,
                                      probability_map=None,
                                      mean_h_norm=None, 
                                      n_objects_range=[1, 6],
                                      h_range=[50, 100],
                                      x_range=[200, 500],
                                      y_range=[100 ,300],
                                      z_range=[0 ,0],
                                      objects_idxs=None,
                                      random_h_flip=True,
                                      random_v_flip=False,
                                      histogram_matching=False,
                                      hm_offset=200,
                                      image_format='bgr',
                                      coords_format='xyxy',
                                      normilized_range=False,
                                      blending_coeff=0):
        
        self.source_images = source_images
        self.bev_transform = bev_transform
        self.n_objects_range = n_objects_range
        self.h_range = h_range
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.objects_idxs = objects_idxs
        self.random_h_flip = random_h_flip
        self.random_v_flip = random_v_flip
        self.image_format = image_format
        self.coords_format = coords_format
        self.normilized_range = normilized_range
        self.probability_map = probability_map
        self.mean_h_norm = mean_h_norm
        self.histogram_matching = histogram_matching
        self.hm_offset = hm_offset
        self.blending_coeff = blending_coeff


    def __call__(self, image):
        return self.generate_objects(image)


    def generate_objects(self, image):
        n_objects = random.randint(*self.n_objects_range)
        if self.probability_map is not None:
            p_h, p_w = self.probability_map.shape
            prob_map_1d = np.squeeze(self.probability_map.reshape((1,-1)))
            select_indexes = np.random.choice(np.arange(prob_map_1d.size), n_objects, p=prob_map_1d)
            points = [[(select_idx%p_w)/p_w, (select_idx//p_w)/p_h] for select_idx in select_indexes]
            points = np.array(points)
            if self.mean_h_norm is not None:
                heights = np.random.uniform(low=self.mean_h_norm*0.98, 
                                            high=self.mean_h_norm*1.02, 
                                            size=(n_objects,1))
            else:
                heights = np.random.uniform(low=self.h_range[0], 
                                            high=self.h_range[1], 
                                            size=(n_objects,1))
        else:
            if self.bev_transform is not None:
                points = np.random.uniform(low=[self.x_range[0], self.y_range[0], self.z_range[0]], 
                                        high=[self.x_range[1], self.y_range[1], self.z_range[1]], 
                                        size=(n_objects, 3))
                heights = np.random.uniform(low=self.h_range[0], 
                                            high=self.h_range[1], 
                                            size=(n_objects,1))
            elif self.normilized_range:
                points = np.random.uniform(low=[self.x_range[0], self.y_range[0]], 
                                        high=[self.x_range[1], self.y_range[1]], 
                                        size=(n_objects, 3))
                heights = np.random.uniform(low=self.h_range[0], 
                                            high=self.h_range[1], 
                                            size=(n_objects,1))

            else:
                points = np.random.randint(low=[self.x_range[0], self.y_range[0]], 
                                        high=[self.x_range[1], self.y_range[1]], 
                                        size=(n_objects,2))
                heights = np.random.randint(low=self.h_range[0], 
                                            high=self.h_range[1], 
                                            size=(n_objects,1))
        
        return self.generate_objects_coord(image, points, heights)


    def generate_objects_coord(self, image, points, heights):
        '''
            points - numpy array of coordinates in meters with shape [n,2]
        '''
        n_objects = points.shape[0]
        
        if self.objects_idxs is None:
            objects_idxs = [random.randint(0,len(self.source_images)-1) for _ in range(n_objects)]
        else:
            objects_idxs = self.objects_idxs
        
        assert len(objects_idxs)==points.shape[0] and points.shape[0]==heights.shape[0]
        
        image_dst = image.copy()
        dst_h, dst_w, _ = image_dst.shape
        coords_all = []
        
        distances = []
        if self.bev_transform is not None:
            points_pixels = self.bev_transform.meters_to_pixels(points)
            distances = self.bev_transform.calculate_dist_meters(points)
            d_sorted_idxs = np.argsort(distances)[::-1]
            distances = distances[d_sorted_idxs]
            heights = heights[d_sorted_idxs]
            z_offsets = points[:,2]
            points = points_pixels[d_sorted_idxs]
        
        semantic_mask = np.zeros((dst_h, dst_w), dtype=np.uint8)
        instance_mask = np.zeros((dst_h, dst_w), dtype=np.uint8)

        for idx, object_idx in enumerate(objects_idxs):
            point = points[idx]
            height = heights[idx]

            image_src = self.select_images(self.source_images, object_idx)
            
            if self.probability_map is not None or self.normilized_range:
                x_coord, y_coord = int(point[0]*dst_w), int(point[1]*dst_h)
                height *= dst_h
                image_src = resize_keep_ar(image_src, height=height)
            else:
                x_coord, y_coord = int(point[0]), int(point[1])
                if self.bev_transform is not None:
                    z_offset = z_offsets[idx]
                    distance = distances[idx]
                    height_pixels = self.bev_transform.get_height_in_pixels(height, distance)
                    height_w_offset_pixels = self.bev_transform.get_height_in_pixels(z_offset+height, distance)
                    pixels_offset = height_w_offset_pixels - height_pixels
                    
                    y_coord -= int(pixels_offset)

                    image_src = resize_keep_ar(image_src, height=height_pixels)
                else:
                    image_src = resize_keep_ar(image_src, height=height)
            
            if self.histogram_matching:
                multi = True if image_src.shape[-1] > 1 else False
                
                image_ref = image[max(0, y_coord-self.hm_offset):min(y_coord+self.hm_offset, dst_h), 
                                  max(0, x_coord-self.hm_offset):min(x_coord+self.hm_offset, dst_w),:]
                ref_h, ref_w, _ = image_ref.shape
                mask_src = image_src[:,:,3]

                if not (ref_h==0 or ref_w==0):
                    image_src = exposure.match_histograms(image_src[:,:,:3], image_ref, multichannel=multi)
                    image_src = cv2.bitwise_and(image_src,image_src,mask=mask_src)
                    image_src = cv2.cvtColor(image_src, cv2.COLOR_BGR2BGRA)
                    image_src[:,:,3] = mask_src

            image_dst, coords, mask = self.paste_object(image_dst, image_src, x_coord, y_coord, self.random_h_flip, self.random_v_flip)
            if coords: 
                coords_all.append(coords)
                x1,y1,x2,y2 = coords
                curr_mask = mask/255
                curr_mask = curr_mask.astype(np.uint8)
                curr_mask_ins = curr_mask*idx

                roi_mask_sem = semantic_mask[y1:y2, x1:x2]
                roi_mask_ins = instance_mask[y1:y2, x1:x2]

                mask_inv = cv2.bitwise_not(curr_mask*255)

                img_sem_bg = cv2.bitwise_and(roi_mask_sem , roi_mask_sem, mask = mask_inv)
                img_ins_bg = cv2.bitwise_and(roi_mask_ins , roi_mask_ins, mask = mask_inv)
                
                dst_sem = cv2.add(img_sem_bg, curr_mask)
                dst_ins = cv2.add(img_ins_bg, curr_mask_ins)

                semantic_mask[y1:y2, x1:x2] = dst_sem
                instance_mask[y1:y2, x1:x2] = dst_ins
        
        coords_all = np.array(coords_all)

        if self.coords_format == 'yolo':
            x = coords_all.copy()
            x = x.astype(float)
            dw = 1./dst_w
            dh = 1./dst_h
            ws = (coords_all[:,2] - coords_all[:,0])
            hs = (coords_all[:,3] - coords_all[:,1])
            x[:,0] = dw * (coords_all[:,0] + ws/2.0)
            x[:,1] = dh * (coords_all[:,1] + hs/2.0)
            x[:,2] = dw * ws
            x[:,3] = dh * hs
            coords_all = x
        elif self.coords_format =='xywh':
            x = coords_all.copy()
            x[:,2] = (coords_all[:,1] - coords_all[:,0])
            x[:,3] = (coords_all[:,3] - coords_all[:,2])
            coords_all = x

        return image_dst, coords_all, semantic_mask, instance_mask


    def select_images(self, source_images, object_idx):
        source_image_path = source_images[object_idx]
        image_src = cv2.imread(str(source_image_path), cv2.IMREAD_UNCHANGED)
        if self.image_format=='rgb':
            image_src = cv2.cvtColor(image_src, cv2.COLOR_BGR2RGBA)
        else:
            image_src = cv2.cvtColor(image_src, cv2.COLOR_BGR2BGRA)
        return image_src


    def paste_object(self, image_dst, image_src, x_coord, y_coord, random_h_flip=True, random_v_flip=False):
        src_h, src_w, _ = image_src.shape
        dst_h, dst_w, _ = image_dst.shape
        x_offset, y_offset = x_coord-int(src_w/2), y_coord-src_h
        y1, y2 = max(y_offset, 0), min(y_offset + src_h, dst_h)
        x1, x2 = max(x_offset, 0), min(x_offset + src_w, dst_w)
        y1_m = 0 if y1>0 else -y_offset
        x1_m = 0 if x1>0 else -x_offset
        y2_m = src_h if y2<dst_h-1 else dst_h - y_offset 
        x2_m = src_w if x2<dst_w-1 else dst_w - x_offset
        coords = []
        
        if y1_m>=src_h or x1_m>=src_w or y2_m<0 or x2_m<0:
            return image_dst, coords, None
        
        if random_h_flip:
            if random.uniform(0, 1)>0.5:
                image_src = cv2.flip(image_src, 1)

        if random_v_flip:
            if random.uniform(0, 1)>0.5:
                image_src = cv2.flip(image_src, 0)

        # Simple cut and paste without preprocessing
        mask_src = image_src[:,:,3]
        if self.blending_coeff>0:
            beta = (1.0 - self.blending_coeff)
            out_img = cv2.addWeighted(image_src[y1_m:y2_m, x1_m:x2_m,:3], self.blending_coeff, image_dst[y1:y2, x1:x2], beta, 0.0)
        else:
            rgb_img =  image_src[:,:,:3]
            mask_inv = cv2.bitwise_not(mask_src)
            img1_bg = cv2.bitwise_and(image_dst[y1:y2, x1:x2],image_dst[y1:y2, x1:x2],mask=mask_inv[y1_m:y2_m, x1_m:x2_m])
            img2_fg = cv2.bitwise_and(rgb_img[y1_m:y2_m, x1_m:x2_m],rgb_img[y1_m:y2_m, x1_m:x2_m],mask=mask_src[y1_m:y2_m, x1_m:x2_m])
            out_img = cv2.add(img1_bg,img2_fg)

        image_dst[y1:y2, x1:x2] = out_img
        coords = [x1,y1,x2,y2]
        mask_visible = mask_src[y1_m:y2_m, x1_m:x2_m]
        
        # Poisson editing
        # kernel = np.ones((5,5),np.uint8)
        # mask_src = cv2.dilate(mask_src, kernel,iterations=2)
        # src_h, src_w, _ = image_src.shape
        # center = (x1+int((x2-x1)/2)), (y1+int((y2-y1)/2))
        # image_dst = cv2.seamlessClone(image_src, image_dst, mask_src, center, cv2.MONOCHROME_TRANSFER )
        
        return image_dst, coords, mask_visible