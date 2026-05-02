import torch
import torch.nn as nn

# -----------------------
# LPRNet MODEL (MINIMAL)
# -----------------------
class LPRNet(nn.Module):
    def __init__(self, num_classes=68):
        super(LPRNet, self).__init__()

        self.backbone = nn.Sequential(
            nn.Conv2d(3, 64, 3, 1, 1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(64, 128, 3, 1, 1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(128, 256, 3, 1, 1),
            nn.ReLU(),

            nn.Conv2d(256, num_classes, 1)
        )

    def forward(self, x):
        return self.backbone(x)


# -----------------------
# LOAD MODEL
# -----------------------
model = LPRNet(num_classes=68)

state_dict = torch.load("Final_LPRNet_model.pth", map_location="cpu")
model.load_state_dict(state_dict, strict=False)

model.eval()

# -----------------------
# EXPORT TO ONNX
# -----------------------
dummy = torch.randn(1, 3, 24, 94)

torch.onnx.export(
    model,
    dummy,
    "lprnet.onnx",
    input_names=["input"],
    output_names=["output"],
    opset_version=11
)

print("✅ Exported to lprnet.onnx")