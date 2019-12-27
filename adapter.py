import json

from fastai.vision import *

from utils.utils import compute_loss

person_cat = 15  # in pascal voc


# Define a custom loss function that translate between FastAI and Ultralytics
def loss_func(model, predicted, boxes, classes):
    # if not model.training:
    #     predicted = predicted[1]
    targets = []
    bs = classes.shape[0]
    max_detections = classes.shape[1]
    for img_idx in range(bs):
        for detect_idx in range(max_detections):
            clazz = classes[img_idx, detect_idx]
            if clazz == 0: continue
            l, t, r, b = boxes[img_idx, detect_idx] * 0.5 + 0.5
            w = r - l
            h = b - t
            targets.append([img_idx, float(clazz - 1), float(l), float(t), float(w), float(h)])
    ft = torch.cuda.FloatTensor if predicted[0].is_cuda else torch.Tensor
    targets = ft(targets)
    loss, _ = compute_loss(predicted, targets, model)
    return loss[0]


# https://github.com/cedrickchee/knowledge/blob/master/courses/fast.ai/deep-learning-part-2/2018-edition/lesson-8-object-detection.md#convert-vocs-bounding-box
def hw_bb(bb):
    return np.array([bb[1], bb[0], bb[3] + bb[1] - 1, bb[2] + bb[0] - 1])


def filename_to_key(filename):
    trunk = os.path.splitext(filename)[0]
    txt = trunk.replace("_", "")
    id = int(txt)
    return id


# Create function for FastAI to get labels
def get_y_func(images, path):
    key = filename_to_key(path.name)
    image = images[key]
    boxes = [hw_bb(a['bbox']) for a in image['annotations'] if a['category_id'] == person_cat]
    classes = ['person'] * len(boxes)
    return [boxes, classes]


def load_voc():
    # Download and untar data
    # https://github.com/cedrickchee/knowledge/blob/master/courses/fast.ai/deep-learning-part-2/2018-edition/lesson-8-object-detection.md
    voc2007 = untar_data(URLs.PASCAL_2007)
    voc2012 = untar_data(URLs.PASCAL_2012)

    # Load images and annotations
    # https://pjreddie.com/darknet/yolo/#train-voc
    files = [
        voc2007 / 'train.json',
        voc2007 / 'valid.json',
        voc2007 / 'test.json',
        voc2012 / 'train.json',
        voc2012 / 'valid.json'
    ]
    jsons = [(it, json.load(it.open())) for it in files]
    images = [{**img, 'file': fn} for (fn, js) in jsons for img in js["images"]]
    images = {i["id"]: i for i in images}
    annotations = [item for (fn, js) in jsons for item in js["annotations"]]

    # Normalize data, slap annotations onto images to which they belong
    for anno in annotations:
        image = images[anno['image_id']]
        image.setdefault('annotations', []).append(anno)

    return images


def has_person(img):
    return [] != [a for a in img['annotations'] if a['category_id'] == person_cat]


def get_folder(f):
    if 'train' in str(f) or 'valid' in str(f): return 'train'
    return 'test'


def make_path(p):
    return p['file'].parent / get_folder(p['file']) / p['file_name']


def json_to_paths(samples):
    posix_paths = [make_path(p) for p in samples]
    return posix_paths


def split_func(sample):
    return '2007' in str(sample['file'].parent) and 'test' in str(sample['file'])


def create_split_func(samples):
    valid = set()
    for sample in samples:
        if split_func(sample):
            valid.add(make_path(sample))
    return lambda it: it in valid
