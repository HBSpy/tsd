import torch
import torch.nn as nn
from ..utils import PositionalEmbedding, RankEmbedding
import numpy as np


class RelationModule(nn.Module):
    def __init__(self,n_relations = 16, appearance_feature_dim=1024,key_feature_dim = 64, geo_feature_dim = 64, isDuplication = False):
        super(RelationModule, self).__init__()
        self.isDuplication=isDuplication
        self.Nr = n_relations
        self.dim_g = geo_feature_dim
        self.relation = nn.ModuleList()
        for N in range(self.Nr):
            self.relation.append(RelationUnit(appearance_feature_dim, key_feature_dim, geo_feature_dim))
    def forward(self, input_data, distance_weight = None):
        if(self.isDuplication):
            f_a, embedding_f_a, position_embedding =input_data
        else:
            f_a, position_embedding = input_data
        isFirst=True
        for N in range(self.Nr):
            if(isFirst):
                if(self.isDuplication):
                    concat = self.relation[N](embedding_f_a,position_embedding, distance_weight)
                else:
                    concat = self.relation[N](f_a,position_embedding, distance_weight)
                isFirst=False
            else:
                if(self.isDuplication):
                    concat = torch.cat((concat, self.relation[N](embedding_f_a, position_embedding, distance_weight)), -1)
                else:
                    concat = torch.cat((concat, self.relation[N](f_a, position_embedding, distance_weight)), -1)
        return concat+f_a
class RelationUnit(nn.Module):
    def __init__(self, appearance_feature_dim=1024,key_feature_dim = 64, geo_feature_dim = 64):
        super(RelationUnit, self).__init__()
        self.dim_g = geo_feature_dim
        self.dim_k = key_feature_dim
        self.WG = nn.Linear(geo_feature_dim, 1, bias=True)
        self.WK = nn.Linear(appearance_feature_dim, key_feature_dim, bias=True)
        self.WQ = nn.Linear(appearance_feature_dim, key_feature_dim, bias=True)
        self.WV = nn.Linear(appearance_feature_dim, key_feature_dim, bias=True)
        self.relu = nn.ReLU(inplace=True)


    def forward(self, f_a, position_embedding, distance_weight = None):
        N,_ = f_a.size()

        position_embedding = position_embedding.view(-1,self.dim_g)

        w_g = self.relu(self.WG(position_embedding))
        w_k = self.WK(f_a)
        w_k = w_k.view(N,1,self.dim_k)

        w_q = self.WQ(f_a)
        w_q = w_q.view(1,N,self.dim_k)

        scaled_dot = torch.sum((w_k*w_q),-1 )
        scaled_dot = scaled_dot / np.sqrt(self.dim_k) # wa(mn) N * N

        w_g = w_g.view(N,N) #wg(mn) N * N
        w_a = scaled_dot.view(N,N)

        w_mn = torch.log(torch.clamp(w_g, min = 1e-6)) + w_a
        if distance_weight is not None:
            zeros = torch.zeros(distance_weight.size()).cuda();
            distance_weight = torch.where(distance_weight > 0.2, distance_weight, zeros)
            # w_mn = w_mn +  torch.log(torch.clamp(distance_weight, min = 1e-6))
            w_mn = w_mn +  torch.log(distance_weight)
        w_mn = torch.nn.Softmax(dim=1)(w_mn)  #w(mn) N * N

        w_v = self.WV(f_a)

        w_mn = w_mn.view(N,N,1)
        w_v = w_v.view(1,N,-1)

        output = w_mn*w_v

        output = torch.sum(output,-2)
        return output