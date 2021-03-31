from torch.utils import data
import os
import torch
import numpy as np
import scipy.misc as m


# +
def recursive_glob(rootdir=".", suffix=""):
    return [
        os.path.join(looproot, filename)
        for looproot, _, filenames in os.walk(rootdir)
        for filename in filenames
        if filename.endswith(suffix)
    ]

class cityscapesLoader(data.Dataset):
    
    colors = [
        [128, 64, 128], [244, 35, 232], [70, 70, 70],
        [102, 102, 156], [190, 153, 153], [153, 153, 153], [250, 170, 30],
        [220, 220, 0], [107, 142, 35], [152, 251, 152], [0, 130, 180],
        [220, 20, 60], [255, 0, 0], [0, 0, 142], [0, 0, 70],
        [0, 60, 100], [0, 80, 100], [0, 0, 230], [119, 11, 32],
    ]
    
    label_colours = dict(zip(range(19), colors)) # mapping colors and labels
    mean_rgb = {
        "pascal": [103.939, 116.779, 123.68],
        "cityscapes": [0.0, 0.0, 0.0],
    }  
    
    def __init__(
        self,
        root,
        split="train",
        is_transform=False,
        img_size=(256, 256),
        augmentations=None,
        img_norm=True,
        version="cityscapes",
        test_mode=False,
    ):
        self.root = root
        self.split = split
        self.is_transform = is_transform
        self.augmentations = augmentations
        self.img_norm = img_norm
        self.n_classes = 19
        self.img_size = img_size if isinstance(img_size, tuple) else (img_size, img_size)
        self.mean = np.array(self.mean_rgb[version])
        self.files = {}
        
        self.images_base = os.path.join(self.root, "leftImg8bit", self.split)
        self.annotations_base = os.path.join(self.root, "gtFine", self.split)
        self.files[split] = recursive_glob(rootdir=self.images_base, suffix=".png")
        
        self.void_classes = [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 16, 18, 29, 30, -1] # Invalid Classes
        self.valid_classes = [7, 8, 11, 12, 13, 17, 19, 20, 21, 22, 23, 24, 25,
                              26, 27, 28, 31, 32, 33]
        
        self.class_names = ["unlabelled", 
                            "road", "sidewalk", "building",
                            "wall", "fence", "pole", "traffic_light",
                            "traffic_sign", "vegetation", "terrain", "sky",
                            "person", "rider", "car", "truck", "bus",
                            "train", "motorcycle", "bicycle"
                           ] 
        self.ignore_index = 250
        self.class_map = dict(zip(self.valid_classes, range(0,19))) 
        
        if not self.files[split]:
            raise Exception("No files for split=[%s] found in %s" % (split, self.images_base))
        
        print("Found %d %s images" % (len(self.files[split]), split))
    
    def __len__(self):
        return len(self.files[self.split])+0
    
    def __getitem__(self, index):

        img_path = self.files[self.split][index].rstrip()
        lbl_path = os.path.join(
            self.annotations_base,
            img_path.split(os.sep)[-2],
            os.path.basename(img_path)[:-15] + "gtFine_labelIds.png",
        )
        
        img = m.imread(img_path)
        img = np.array(img, dtype=np.uint8) # h*w*c
        
        lbl = m.imread(lbl_path)
        lbl = self.encode_segmap(np.array(lbl, dtype=np.uint8))
        
        if self.augmentations is not None:
            img, lbl = self.augmentations(img, lbl)
        
        if self.is_transform:
            img, lbl = self.transform(img, lbl)
        
        return img, lbl
    
    def transform(self, img, lbl):

        if(type(img) == torch.Tensor):
            img = img.numpy()
        if(type(lbl) == torch.Tensor):
            lbl = lbl.numpy()
        
        img = m.imresize(img, (self.img_size[0], self.img_size[1]))  # uint8 with RGB mode
        img = img[:, :, ::-1]  # RGB -> BGR(::-1 is flip reading, here refers to the one-dimensional reverse reading of the channel, which is convenient for OpenCV)
        img = img.astype(np.float64)
        img -= self.mean
        
        if self.img_norm:
            # Resize scales images from 0 to 255, thus we need
            # to divide by 255.0
            img = img.astype(float) / 255.0
        # NHWC -> NCHW
        img = img.transpose(2, 0, 1)
        
        classes = np.unique(lbl)
        lbl = lbl.astype(float)
        lbl = m.imresize(lbl, (self.img_size[0], self.img_size[1]), "nearest", mode="F")
        lbl = lbl.astype(int)
                
        if not np.all(np.unique(lbl[lbl != self.ignore_index]) < self.n_classes):
            print("after det", classes, np.unique(lbl))
            raise ValueError("Segmentation map contained invalid class values")
        
        img = torch.from_numpy(img).float()
        lbl = torch.from_numpy(lbl).long()
        
        return img, lbl
    
    def decode_segmap(self, temp): # Colour according to category
        r = temp.copy()
        g = temp.copy()
        b = temp.copy()
        
        for l in range(0, self.n_classes):
            r[temp == l] = self.label_colours[l][0]
            g[temp == l] = self.label_colours[l][1]
            b[temp == l] = self.label_colours[l][2]
        
        rgb = np.zeros((temp.shape[0], temp.shape[1], 3)) # creating a matrix for the mask in rgb
        rgb[:, :, 0] = r / 255.0
        rgb[:, :, 1] = g / 255.0
        rgb[:, :, 2] = b / 255.0
        
        return rgb

    def encode_segmap(self, mask): # Removing the invalid classes
        for _voidc in self.void_classes:
            mask[mask == _voidc] = self.ignore_index
        for _validc in self.valid_classes:
            mask[mask == _validc] = self.class_map[_validc]
        return mask