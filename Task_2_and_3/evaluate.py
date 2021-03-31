import torch
import numpy as np
from tqdm import tqdm
from sklearn import metrics
from utils import load_checkpoint
from metrics import eval_metrics
import torch.nn.functional as F


# Modified Cross-Entropy loss
def CE_loss(output, target):
    n, c, h, w = output.size()
    nt, ht, wt = target.size()
    assert c == 20
    if (h != ht and w != wt):
        output = F.interpolate(output, size=(ht, wt), mode="bilinear", align_corners=True)

    output = output.transpose(1, 2).transpose(2, 3).contiguous()
    target[target == 250] = 19

    for i in range(target.size(0)):
        if i == 0:
            loss = (F.cross_entropy(output[i].view(-1, c), target[i].view(-1), reduction='none')).mean()
        else:
            loss += (F.cross_entropy(output[i].view(-1, c), target[i].view(-1), reduction='none')).mean()
    return loss


def evaluation(checkpoint_path, dataset, loader, bs, model, device, num_classes):

    load_checkpoint(checkpoint_path, model)
    model.eval()

    avg_jacc_final = 0
    avg_dice_final = 0
    f1_score_final = 0
    acc_final = 0
    auc_final = 0

    num_batches = int(len(dataset)/bs) # len(traindataset) is the total train images and bs is the batch_size 

    with torch.no_grad():
        for batch_idx, (images, labels) in enumerate(tqdm(loader)):
            images, labels = images.to(device), labels.to(device)            
            output = torch.sigmoid(model(images))
            output_2d = torch.argmax(output, dim=1).detach().cpu()
            labels = labels.cpu()
            avg_jacc, avg_dice, f1_score, ov_acc, auc_sc = eval_metrics(labels, output_2d, num_classes=num_classes, batch_sz=bs)
            avg_jacc_final += avg_jacc.numpy()
            avg_dice_final += avg_dice.numpy()
            f1_score_final += f1_score
            acc_final += ov_acc
            auc_final += auc_sc

    print(f'avg_jacc or iou: {avg_jacc_final/num_batches},\
    avg_dice: {avg_dice_final/num_batches}, f1_score: {f1_score_final/num_batches},\
    accuracy: {acc_final/num_batches}, auc: {auc_final/num_batches}')
    
    return avg_jacc_final/num_batches, avg_dice_final/num_batches, f1_score_final/num_batches, acc_final/num_batches, auc_final/num_batches 
