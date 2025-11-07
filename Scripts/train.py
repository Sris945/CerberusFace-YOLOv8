from ultralytics import YOLO
import torch
import matplotlib.pyplot as plt
import os

def train_yolov8_high_accuracy():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f" Training on: {device}")

    # Load base model
    model = YOLO("yolov8n.pt")  

    # Config
    train_cfg = {
        "data": "/datasets/data.yaml",         # path to your data.yaml
        "epochs": 200,                  # number of epochs to train
        "imgsz": 640,               # input image size
        "device": 0,           # GPU device id (0 for first GPU, 'cpu' for CPU) 
        "workers": 4,
        "patience": 20,
        "batch": 16,                  # batch size
        "optimizer": "AdamW",
        "lr0": 0.001,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_epochs": 3,
        "warmup_momentum": 0.8,
        "warmup_bias_lr": 0.1,
        "project": "runs/train",
        "name": "yolo_faces_highacc",
        "exist_ok": True,
        "cache": "disk",            # 'ram' for faster, 'disk' for stability
        "save": True,
        "save_period": 10,
        "box": 7.5,
        "cls": 0.5,
        "dfl": 1.5,
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4,
        "degrees": 0.0,
        "translate": 0.1,
        "scale": 0.5,
        "shear": 0.0,
        "perspective": 0.0,
        "flipud": 0.0,
        "fliplr": 0.5,
        "mosaic": 1.0,
        "mixup": 0.2,
        "copy_paste": 0.2,
    }

    print(" Starting training...")
    results = model.train(**train_cfg)

    # Path to training folder
    save_dir = results.save_dir

    # Plot training results (loss, mAP, precision/recall, etc.)
    results_path = os.path.join(save_dir, "results.png")
    if os.path.exists(results_path):
        print(" Plotting training metrics...")
        img = plt.imread(results_path)
        plt.imshow(img)
        plt.axis("off")
        plt.title("YOLOv8 Training Metrics")
        plt.show()
    else:
        print(" results.png not found – model may not have saved plots.")

    #  Validate trained model
    print(" Validating model...")
    metrics = model.val()
    print("Validation metrics:")
    print(metrics)

    #  Export model (optional)
    print(" Exporting to ONNX...")
    model.export(format="onnx")

    print(f" Training done. Model saved to: {save_dir}/weights/best.pt")
    return model

if __name__ == "__main__":
    train_yolov8_high_accuracy()
