import torch
import torch.optim as optim
import numpy as np
import matplotlib.pyplot as plt
import cv2

from Model.model_hgsr import HourGlassNetMultiScaleInt
from loss import get_content_loss, GW_loss
from simplenet import simpleNet

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('\nUsing device:', device)
cntr = 0
for i in range(91, 101):
    print(f"Data Number: {cntr}\n")
    X_name = "/home/emrecan/Desktop/Comp411/data/BSD100/" + "img_" + str(i).zfill(3) + "_SRF_4_LR.png"
    Y_name = "/home/emrecan/Desktop/Comp411/data/BSD100/" + "img_" + str(i).zfill(3) + "_SRF_4_HR.png"
    output_file = '/home/emrecan/Desktop/Comp411/data/results/BSD100/' + "img_" + str(i).zfill(3) + "_SRF_4.png"

    X = cv2.imread(X_name)[:,:,::-1]
    Y = cv2.imread(Y_name)[:,:,::-1]

    wx, hx, c = X.shape
    wx = (wx//4)*4
    hx = (hx//4)*4
    X = X[:wx, :hx, :]
    Y = Y[:(4*wx), :(4*hx), :]
    X_original = X
    Y_original = Y
    X = X.astype(float)
    Y = Y.astype(float)
    X /= 255.0
    Y /= 255.0

    # Bi-CUBIC interpolation
    lr_son = cv2.resize(X, None,fx=0.25, fy=0.25, interpolation=cv2.INTER_CUBIC)

    lr_son_tensor = torch.FloatTensor(lr_son)
    lr_father_tensor = torch.FloatTensor(X)
    HR_tensor = torch.FloatTensor(Y)

    lr_son, lr_father, HR = lr_son_tensor.unsqueeze(0), lr_father_tensor.unsqueeze(0), HR_tensor.unsqueeze(0)
    lr_son, lr_father, HR = lr_son.permute(0, 3, 1, 2), lr_father.permute(0, 3, 1, 2), HR.permute(0, 3, 1, 2)

    # Training
    EPOCHS = 20000
    LR = 2e-5

    model = simpleNet()
    model.to(device)
    optimizer = optim.AdamW(model.parameters(), lr=LR)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min')
    inte_loss_weight = torch.Tensor([1.0, 2.0, 5.0, 1.0])
    content_criterion = get_content_loss("L2", nn_func=False, use_cuda=True)

    for epoch in range(EPOCHS):

        lr_FATHER = (0.257 * lr_father[:, :1, :, :] + 0.564 * lr_father[:, 1:2, :, :] + 0.098 * lr_father[:, 2:, :,:] + 16 / 255.0) * 255.0
        map_corner = lr_FATHER.new(lr_FATHER.shape).fill_(0)
        map_edge = lr_FATHER.new(lr_FATHER.shape).fill_(0)
        map_flat = lr_FATHER.new(lr_FATHER.shape).fill_(0)
        lr_FATHER_numpy = np.transpose(lr_FATHER.numpy(), (0, 2, 3, 1))
        for i in range(lr_FATHER_numpy.shape[0]):
            dst = cv2.cornerHarris(lr_FATHER_numpy[i, :, :, 0], 3, 3, 0.04)
            thres1 = 0.01 * dst.max()
            thres2 = -0.001 * dst.max()
            map_corner[i, :, :, :] = torch.from_numpy(np.float32(dst > thres1))
            map_edge[i, :, :, :] = torch.from_numpy(np.float32(dst < thres2))
            map_flat[i, :, :, :] = torch.from_numpy(np.float32((dst > thres2) & (dst < thres1)))
        map_corner = map_corner.to(device)
        map_edge = map_edge.to(device)
        map_flat = map_flat.to(device)
        coe_list = []
        coe_list.append(map_flat)
        coe_list.append(map_edge)
        coe_list.append(map_corner)

        sr_var = model(lr_son.to(device))

        sr_loss = 0
        if isinstance(sr_var, list):
            for i in range(len(sr_var)):
                if i != len(sr_var) - 1:
                    coe = coe_list[i].to(device)
                    single_srloss = inte_loss_weight[i] * content_criterion(coe * sr_var[i], coe * (lr_father.to(device)))
                else:
                    single_srloss = inte_loss_weight[i] * GW_loss(sr_var[i], (lr_father.to(device)))
                sr_loss += single_srloss
        else:
            sr_loss = content_criterion(sr_var, (lr_father.to(device)))

        optimizer.zero_grad()
        sr_loss.backward()
        optimizer.step()
        print(f"Epoch: {epoch}/{EPOCHS}, loss:{sr_loss}")

    pred = model(lr_son.to(device))
    pred_ = pred.permute(0, 2, 3, 1).squeeze(0)
    predd = pred_.cpu().detach().numpy()
    predd = np.clip(predd, 0, 1)*255
    preddd = np.uint8(predd)
    inp = lr_father.to(device)
    pred2 = model(inp)
    pred3 = pred2.permute(0, 2, 3, 1).squeeze(0)
    pred4 = pred3.cpu().detach().numpy()
    pred5 = np.clip(pred4, 0, 1)*255
    pred6 = np.uint8(pred5)
    cv2.imwrite(output_file, pred6[:,:,::-1])

    cntr += 1

