import math
import torch
import random
import torch.nn.functional as AFs
import torch.nn as nn
import settings
import numpy as np


class SReLU():
    def __init__(self):
        super(SReLU, self).__init__()
    def forward(self,t_right ,t_left,a_left,a_right,x):
        # ensure the the right part is always to the right of the left
        y_left = -torch.nn.ReLU()(-x+t_left) * a_left
        mid = (torch.nn.ReLU()(x-t_left))-(torch.nn.ReLU()(x-t_right))
        y_right = torch.nn.ReLU()(x - t_right) * a_right
        return y_left + y_right + mid

class MetaAconC(nn.Module):
    r""" ACON activation (activate or not).
    # MetaAconC: (p1*x-p2*x) * sigmoid(beta*(p1*x-p2*x)) + p2*x, beta is generated by a small network
    # according to "Activate or Not: Learning Customized Activation" <https://arxiv.org/pdf/2009.04759.pdf>.
    """
    def __init__(self, width, r=16):
        super().__init__()
        self.fc1 = nn.Conv2d(width, max(r, width // r), kernel_size=1, stride=1, bias=True)
        self.bn1 = nn.BatchNorm2d(max(r, width // r))
        self.fc2 = nn.Conv2d(max(r, width // r), width, kernel_size=1, stride=1, bias=True)
        self.bn2 = nn.InstanceNorm1d(width)
        self.p1 = nn.Parameter(torch.randn(1, width, 1, 1))
        self.p2 = nn.Parameter(torch.randn(1, width, 1, 1))

    def forward(self, x, active):
        beta = torch.sigmoid(self.bn2(self.fc2(self.fc1(x.view([1,len(x),1,1]))).view([1,len(x)])).view([len(x)]))
        return (self.p1 * x - self.p2 * x) * torch.sigmoid(beta * (self.p1 * x - self.p2 * x)) + self.p2 * x


# simply define a silu function
def srs(input, a, b):
    return torch.div(input, (input/a + torch.exp(-input/b))) 
    # use torch.sigmoid to make sure that we created the most efficient implemetation based on builtin PyTorch functions
class SRS(nn.Module):
    def __init__(self):
        super().__init__() # init the base class
    def forward(self, input ,a ,b):
        return srs(input,a ,b)



def ash(x, k_ash_):
    result = []
    for input in x:
        input1 = input.cpu()
        input1 = input1.detach().numpy()
        th = np.percentile(input1, int((1 - k_ash_) * 100))
        m = nn.Threshold(th, 0)
        result.append(m(input))
    for i in range(len(x)):
        x[i] = result[i]
    return x

class ASH(nn.Module):
    def __init__(self):
        super().__init__() # init the base class
    def forward(self, input, k_ash_):
        return ash(input, k_ash_)
def swish_(t):
    return (t)*torch.sigmoid(t)

def sig_(t):
    return torch.sigmoid(t)

def D1(t,alpha):
    return swish_(t) + alpha*sig_(t)*(1-swish_(t) )

def D2(t,alpha):
  return D1(t,1) + alpha*sig_(t)*(1-2*D1(t,1))


class Common_Activation_Function(nn.Module):
    def __init__(self, acon_size=None,p1=1,p2=1,p3=1,p4=1,p5=1): #TODO:
        super(Common_Activation_Function, self).__init__()
        self.acon_size = acon_size
        # initialize parameters
        self.p1 = nn.Parameter(torch.tensor(float(p1)), requires_grad=False)
        self.p2 = nn.Parameter(torch.tensor(float(p2)), requires_grad=False)
        self.p3 = nn.Parameter(torch.tensor(float(p3)), requires_grad=False)
        self.p4 = nn.Parameter(torch.tensor(float(p4)), requires_grad=False)
        self.p5 = nn.Parameter(torch.tensor(float(p5)), requires_grad=False)

    def hard_sigmoid(self, x):
        x = (0.2 * x) + 0.5
        x = AFs.threshold(-x, -1, -1)
        x = AFs.threshold(-x, 0, 0)
        return x



    def Unary_Operator(self, x, activation):

        if activation == 'linear':
            return self.p1 * x
        if activation == 'FALU':
            if self.p1>=1:
                return D2(self.p2*x,self.p1-1)
            elif self.p1<1:
                return D1(self.p2*x,self.p1)
        elif activation == 'symlog':
            return self.p1*torch.sign(self.p2*x)*torch.log(abs(self.p2*x)+1)
        elif activation == 'symexp':
            return self.p1*torch.sign(self.p2*x)*(torch.exp(abs(self.p2*x))-1)
        elif activation == 'SRelu':
            return SReLU().forward(self.p1, self.p2, self.p3, self.p4, x)
        elif activation == 'meta_acon': #TODO:
            return MetaAconC(self.acon_size)(x)
        elif activation == 'acon':
            return (self.p1 * x - self.p2 * x) * torch.sigmoid(self.p3 * (self.p1 * x - self.p2 * x)) + self.p2 * x
        elif activation == 'TanhSoft-1':
            return nn.Tanh()(self.p1*x) * nn.Softplus()(x)
        elif activation == 'TanhSoft-2':
            return x * nn.Tanh()(self.p1 * torch.exp(self.p2 * x))
        elif activation == 'ash': #TODO:test
            return ASH()(x, self.p1)
        elif activation == 'srs':#TODO:test
            return SRS()(x, self.p1, self.p2)
        elif activation == 'mish':
            return self.p1 * nn.Mish()(self.p2 * x)
        elif activation == 'relu6':
            return self.p1 * nn.ReLU6()(self.p2 * x)
        elif activation == 'hardswish':
            return self.p1 * nn.Hardswish()(self.p2 * x)
        elif activation == 'elu':
            return self.p1 * AFs.elu(self.p2 * x)
        elif activation == 'relu':
            return self.p1 * AFs.relu(self.p2 * x)
        elif activation == 'selu':
            return self.p1 * AFs.selu(self.p2 * x)
        elif activation == 'tanh':
            return self.p1 * torch.tanh(self.p2 * x)
        elif activation == 'sigmoid':
            return self.p1 * torch.sigmoid(self.p2 * x)
        elif activation == 'logsigmiod':
            return self.p1 * AFs.logsigmoid(self.p2 * x)
        elif activation == 'hardtan':
            return self.p1 * AFs.hardtan(self.p2 * x)
        elif activation == 'softplus':
            return self.p1 * AFs.softplus(self.p2 * x)
        elif activation == 'swish':
            return self.p1 * torch.sigmoid(self.p2 * x) * x
        elif activation == 'sin':
            return self.p1 * torch.sin(self.p2 * x)
        elif activation == 'cos':
            return self.p1 * torch.cos(self.p2 * x)
        elif activation == 'gelu':
            return self.p1 * nn.GELU()(self.p2 * x)
        elif activation == 'elish':
            return self.p1 * torch.where(x < 0, AFs.elu(self.p2 * x) * torch.sigmoid(self.p2 * x), torch.sigmoid(self.p2 * x) * x)
        elif activation == 'hard_elish':
            return self.p1 * torch.where(x < 0.0, AFs.elu(self.p2 * x) * self.hard_sigmoid(self.p2 * x), self.hard_sigmoid(self.p2 * x) * x)
        else:
            print('error:activation type')
            return self.p1 * AFs.relu(self.p2 * x)

    def forward(self, x, activation):
        return self.Unary_Operator(x, activation)

def Activation_Function(name, x):
    return Common_Activation_Function(x)