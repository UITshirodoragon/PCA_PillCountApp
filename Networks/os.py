from __future__ import division, absolute_import
import os
import torch
from torch import nn
from torch.nn import functional as F
from thop import profile, clever_format
from torchsummary import summary
from .PFE import PFE_module


class ConvLayer(nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        kernel_size,
        stride=1,
        padding=0,
        groups=1
    ):
        super(ConvLayer, self).__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            bias=False,
            groups=groups
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x


class Conv1x1(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1, groups=1):
        super(Conv1x1, self).__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            1,
            stride=stride,
            padding=0,
            bias=False,
            groups=groups
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x


class Conv1x1Linear(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super(Conv1x1Linear, self).__init__()
        self.conv = nn.Conv2d(
            in_channels, out_channels, 1, stride=stride, padding=0, bias=False
        )
        self.bn = nn.BatchNorm2d(out_channels)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        return x


class Conv3x3(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1, groups=1):
        super(Conv3x3, self).__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            3,
            stride=stride,
            padding=1,
            bias=False,
            groups=groups
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x


class LightConv3x3(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(LightConv3x3, self).__init__()
        self.conv1 = nn.Conv2d(
            in_channels, out_channels, 1, stride=1, padding=0, bias=False
        )
        self.conv2 = nn.Conv2d(
            out_channels,
            out_channels,
            3,
            stride=1,
            padding=1,
            bias=False,
            groups=out_channels
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.bn(x)
        x = self.relu(x)
        return x

class ChannelGate(nn.Module):
    def __init__(
        self,
        in_channels,
        num_gates=None,
        return_gates=False,
        gate_activation='sigmoid',
        reduction=16,
        layer_norm=False
    ):
        super(ChannelGate, self).__init__()
        if num_gates is None:
            num_gates = in_channels
        self.return_gates = return_gates
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(
            in_channels,
            in_channels // reduction,
            kernel_size=1,
            bias=True,
            padding=0
        )
        self.norm1 = None
        if layer_norm:
            self.norm1 = nn.LayerNorm((in_channels // reduction, 1, 1))
        self.relu = nn.ReLU(inplace=True)
        self.fc2 = nn.Conv2d(
            in_channels // reduction,
            num_gates,
            kernel_size=1,
            bias=True,
            padding=0
        )
        if gate_activation == 'sigmoid':
            self.gate_activation = nn.Sigmoid()
        elif gate_activation == 'relu':
            self.gate_activation = nn.ReLU(inplace=True)
        elif gate_activation == 'linear':
            self.gate_activation = None
        else:
            raise RuntimeError(
                "Unknown gate activation: {}".format(gate_activation)
            )

    def forward(self, x):
        input = x
        x = self.global_avgpool(x)
        x = self.fc1(x)
        if self.norm1 is not None:
            x = self.norm1(x)
        x = self.relu(x)
        x = self.fc2(x)
        if self.gate_activation is not None:
            x = self.gate_activation(x)
        if self.return_gates:
            return x
        return input * x


class OSBlock(nn.Module):
    def __init__(self, in_channels, out_channels, **kwargs):
        super(OSBlock, self).__init__()
        mid_channels = out_channels // 4
        self.conv1 = Conv1x1(in_channels, mid_channels)
        self.conv2a = LightConv3x3(mid_channels, mid_channels)
        self.conv2b = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.conv2c = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.conv2d = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.gate = ChannelGate(mid_channels)
        self.conv3 = Conv1x1Linear(mid_channels, out_channels)
        self.downsample = None
        if in_channels != out_channels:
            self.downsample = Conv1x1Linear(in_channels, out_channels)

    def forward(self, x):
        residual = x
        x1 = self.conv1(x)
        x2a = self.conv2a(x1)
        x2b = self.conv2b(x1)
        x2c = self.conv2c(x1)
        x2d = self.conv2d(x1)
        x2 = self.gate(x2a) + self.gate(x2b) + self.gate(x2c) + self.gate(x2d)
        x3 = self.conv3(x2)
        if self.downsample is not None:
            residual = self.downsample(residual)
        out = x3 + residual
        return F.relu(out)

class BaseNet(nn.Module):
    def _make_layer(
        self, block, layer, in_channels, out_channels, reduce_spatial_size
    ):
        layers = []

        layers.append(block(in_channels, out_channels))
        for i in range(1, layer):
            layers.append(block(out_channels, out_channels))

        if reduce_spatial_size:
            layers.append(
                nn.Sequential(
                    Conv1x1(out_channels, out_channels),
                    nn.AvgPool2d(2, stride=2)
                )
            )
        return nn.Sequential(*layers)

    def _construct_fc_layer(self, fc_dims, input_dim, dropout_p=None):
        if fc_dims is None or fc_dims < 0:
            self.feature_dim = input_dim
            return None

        if isinstance(fc_dims, int):
            fc_dims = [fc_dims]

        layers = []
        for dim in fc_dims:
            layers.append(nn.Linear(input_dim, dim))
            layers.append(nn.BatchNorm1d(dim))
            layers.append(nn.ReLU(inplace=True))
            if dropout_p is not None:
                layers.append(nn.Dropout(p=dropout_p))
            input_dim = dim

        self.feature_dim = fc_dims[-1]

        return nn.Sequential(*layers)

    def init_params(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu'
                )
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

            elif isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
                    
class OSNet(BaseNet):
    def __init__(
        self,
        num_classes,
        blocks,
        layers,
        channels,
        feature_dim=512,
        loss='softmax',
        pool='avg',
        **kwargs
    ):
        super(OSNet, self).__init__()
        num_blocks = len(blocks)
        assert num_blocks == len(layers)
        assert num_blocks == len(channels) - 1
        self.loss = loss

        self.conv1 = ConvLayer(3, channels[0], 7, stride=2, padding=3)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.conv2 = self._make_layer(
            blocks[0],
            layers[0],
            channels[0],
            channels[1],
            reduce_spatial_size=True
        )
        self.conv3 = self._make_layer(
            blocks[1],
            layers[1],
            channels[1],
            channels[2],
            reduce_spatial_size=True
        )
        self.conv4 = self._make_layer(
            blocks[2],
            layers[2],
            channels[2],
            channels[3],
            reduce_spatial_size=False
        )
        self.conv5 = Conv1x1(channels[3], channels[3])

    def forward(self, x):
        x = self.conv1(x)
        x = self.maxpool(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.conv5(x)
        
        return x

def load_osnet_weights(channels, model_path):
    net = OSNet(
        num_classes=1000,
        blocks=[OSBlock, OSBlock, OSBlock],
        layers=[2, 2, 2],
        channels=channels,
        loss='softmax',
    )
    state_dict = torch.load(model_path, map_location="cpu")
    for key in (
        "fc.0.weight",
        "fc.0.bias",
        "fc.1.weight",
        "fc.1.bias",
        "fc.1.running_mean",
        "fc.1.running_var",
        "fc.1.num_batches_tracked",
        "classifier.weight",
        "classifier.bias",
    ):
        state_dict.pop(key, None)

    net.load_state_dict(state_dict)
    return net


class PANet(nn.Module):
    def __init__(
        self,
        channels=(64, 256, 384, 512),
        osnet_weight_path="./Networks/OSNet/osnet_x1_0_imagenet.pth",
        decoder_channels=(256, 128, 64, 32),
    ):
        super(PANet, self).__init__()
        self.vgg = load_osnet_weights(list(channels), osnet_weight_path)
        self.lms = PFE_module(int(channels[-1]))
        c0, c1, c2, c3 = [int(c) for c in decoder_channels]
        self.de_pred = nn.Sequential(
                            nn.ConvTranspose2d(c0,c1,4,stride=2,padding=1,output_padding=0,bias=True),
                            nn.ReLU(),
                            nn.ConvTranspose2d(c1,c2,4,stride=2,padding=1,output_padding=0,bias=True),
                            nn.ReLU(),
                            nn.ConvTranspose2d(c2,c3,4,stride=2,padding=1,output_padding=0,bias=True),
                            nn.ReLU(),
                            nn.ConvTranspose2d(c3,1,4,stride=2,padding=1,output_padding=0,bias=True),
                            )
    def forward(self, x):
        x = self.vgg(x)
        x = self.lms(x)
        x = self.de_pred(x)
        return x


class PANetBase(PANet):
    def __init__(self):
        super(PANetBase, self).__init__(
            channels=(64, 256, 384, 512),
            osnet_weight_path="./Networks/OSNet/osnet_x1_0_imagenet.pth",
            decoder_channels=(256, 128, 64, 32),
        )


class PANetNano(PANet):
    def __init__(self):
        super(PANetNano, self).__init__(
            channels=(16, 64, 96, 128),
            osnet_weight_path="./Networks/OSNet/osnet_x0_25_imagenet.pth",
            decoder_channels=(64, 32, 16, 8),
        )






def count_params(model):
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable


def split_param_buckets(model: nn.Module):
    buckets = {
        "backbone(OSNet)": 0,
        "PFE_module": 0,
        "decoder(de_pred)": 0,
        "others": 0
    }
    for name, p in model.named_parameters():
        n = p.numel()
        if name.startswith("vgg."):
            buckets["backbone(OSNet)"] += n
        elif name.startswith("lms.") or "pfe" in name.lower():
            buckets["PFE_module"] += n
        elif name.startswith("de_pred."):
            buckets["decoder(de_pred)"] += n
        else:
            buckets["others"] += n
    return buckets

if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # 1) Khởi tạo model
    model = PANet().to(device).eval()

    # (tùy chọn) 2) Nạp weight cho OSNet nếu bạn có sẵn


    # 3) Kích thước input dùng để profile/summary
    #    Đổi lại cho khớp với pipeline của bạn (ví dụ 256x256 hoặc 576x768)
    C, H, W = 3, 256, 256

    # 4) Tổng tham số
    total, trainable = count_params(model)
    print(f"\n== PARAMS ==")
    print(f"Total params:     {total:,}")
    print(f"Trainable params: {trainable:,}")

    # 5) Phân rã tham số theo khối lớn
    buckets = split_param_buckets(model)
    print("\n== PARAM BUCKETS ==")
    for k, v in buckets.items():
        pct = (v / total * 100.0) if total > 0 else 0.0
        print(f"{k:<20}: {v:,}  ({pct:.2f}%)")

    # 6) FLOPs/MACs với thop
    dummy = torch.randn(1, C, H, W).to(device)
    macs, params = profile(model, inputs=(dummy,), verbose=False)  # macs ~ multiply-accumulates
    macs_str, params_str = clever_format([macs, params], "%.3f")
    # Quy ước thường dùng: FLOPs ≈ 2 * MACs (nhưng nhiều paper báo "FLOPs" = MACs).
    print(f"\n== COMPUTE ==")
    print(f"MACs:  {macs_str}")
    print(f"FLOPs (≈2*MACs): {clever_format([macs*2], '%.3f')[0]}")
    print(f"Params (thop):    {params_str}")

    # 7) Tóm lược model theo layer (torchsummary)
    print("\n== TORCHSUMMARY ==")
    summary(model, input_size=(C, H, W), device=str(device))

