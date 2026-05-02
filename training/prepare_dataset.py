import os, shutil, random

SRC = r"C:\Users\visithran\.cache\kagglehub\datasets\gauravsanwal\indian-licence-plate\versions\1\licence plate.v1i.darknet"
DST = r"D:\ANPR\training\dataset"

splits = ['train', 'test']
for split in splits:
    os.makedirs(f"{DST}/images/{split}", exist_ok=True)
    os.makedirs(f"{DST}/labels/{split}", exist_ok=True)

os.makedirs(f"{DST}/images/val", exist_ok=True)
os.makedirs(f"{DST}/labels/val", exist_ok=True)

# Copy test files
test_src = os.path.join(SRC, 'test')
for f in os.listdir(test_src):
    src_path = os.path.join(test_src, f)
    if f.endswith('.jpg'):
        shutil.copy(src_path, f"{DST}/images/test/{f}")
    elif f.endswith('.txt') and f != 'classes.txt':
        shutil.copy(src_path, f"{DST}/labels/test/{f}")

# Split train into train (90%) and val (10%)
train_src = os.path.join(SRC, 'train')
all_images = [f for f in os.listdir(train_src) if f.endswith('.jpg')]
random.shuffle(all_images)

val_count = int(len(all_images) * 0.1)
val_images = all_images[:val_count]
train_images = all_images[val_count:]

print(f"Train: {len(train_images)} | Val: {len(val_images)} | Test: {len(os.listdir(test_src))//2}")

for f in train_images:
    base = f.replace('.jpg', '')
    shutil.copy(f"{train_src}/{f}", f"{DST}/images/train/{f}")
    label = f"{train_src}/{base}.txt"
    if os.path.exists(label):
        shutil.copy(label, f"{DST}/labels/train/{base}.txt")

for f in val_images:
    base = f.replace('.jpg', '')
    shutil.copy(f"{train_src}/{f}", f"{DST}/images/val/{f}")
    label = f"{train_src}/{base}.txt"
    if os.path.exists(label):
        shutil.copy(label, f"{DST}/labels/val/{base}.txt")

print("Done! Dataset ready.")