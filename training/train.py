from ultralytics import YOLO

model = YOLO('yolov8n.pt')

model.train(
    data='training/data.yaml',
    epochs=50,
    imgsz=416,        # reduced from 640 → 3x faster
    batch=16,         # increased → fewer iterations per epoch
    device='cpu',
    project='training/runs',
    name='plate_det_v2',
    patience=10,
    augment=True,
    workers=4
)