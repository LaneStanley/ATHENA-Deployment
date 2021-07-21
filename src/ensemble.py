from absl import app, flags, logging
from absl.flags import FLAGS
import tensorflow as tf
from yolov3_tf2.models import (
    YoloV3, YoloV3Tiny
)
from yolov3_tf2.dataset import transform_images
from yolov3_tf2.utils import draw_outputs, majority_voting

import numpy as np #my thing to flip image
from yolov3_tf2.weak_defences import WeakDefence
import cv2

flags.DEFINE_list('wds', ['clean'], 'type the desired weak defence. type the name multiple times for multiple '
                                         'instances of WD')
flags.DEFINE_integer('gpu', None, 'set which gpu to use')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_string('classes', './data/coco.names', 'path to classes file')
flags.DEFINE_string('image', './data/meme.jpg', 'path to input image')
flags.DEFINE_integer('num_classes', 80, 'number of classes in the model')


def main(_argv):
    physical_devices = tf.config.experimental.list_physical_devices('GPU')
    if (physical_devices != []) and (FLAGS.gpu is not None):
        tf.config.experimental.set_visible_devices(physical_devices[FLAGS.gpu], 'GPU')
        tf.config.experimental.set_memory_growth(physical_devices[FLAGS.gpu], True)
    else:
        tf.config.set_visible_devices([], 'GPU')

    #img_raw = tf.image.decode_image(
    #    open(FLAGS.image, 'rb').read(), channels=3)
    #img = tf.expand_dims(img_raw, 0)
    #img = transform_images(img, FLAGS.size)
    img = cv2.imread(FLAGS.image)

    class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
    logging.info('classes loaded')

    models = []
    for wd in FLAGS.wds:
        wd_model = YoloV3(classes=FLAGS.num_classes)
        weights = f'./checkpoints/yolov3_{wd}/yolov3_{wd}.tf'
        wd_model.load_weights(weights)
        models.append(WeakDefence(wd_model, wd, FLAGS.size))
    logging.info('ensemble loaded')

    boxes = []
    scores = []
    classes = []
    for model in models:
        img_in = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        boxes_temp, scores_temp, classes_temp, _ = model.predict(tf.identity(img_in))
        boxes = np.concatenate((boxes, boxes_temp), axis=1) if np.size(boxes) else boxes_temp
        scores = np.concatenate((scores, scores_temp), axis=1) if np.size(scores) else scores_temp
        classes = np.concatenate((classes, classes_temp), axis=1) if np.size(classes) else classes_temp

    boxes = np.squeeze(boxes, axis=0)
    scores = np.squeeze(scores, axis=0)
    classes = np.squeeze(classes, axis=0)

    selected_indices, selected_scores = tf.image.non_max_suppression_with_scores(
        boxes, scores, max_output_size=100, iou_threshold=0.5, score_threshold=0.5, soft_nms_sigma=0.5)

    num_valid_nms_boxes = tf.shape(selected_indices)[0]

    selected_indices = tf.concat([selected_indices, tf.zeros(FLAGS.yolo_max_boxes - num_valid_nms_boxes, tf.int32)], 0)
    selected_scores = tf.concat([selected_scores, tf.zeros(FLAGS.yolo_max_boxes - num_valid_nms_boxes, tf.float32)], -1)

    boxes = tf.gather(boxes, selected_indices)
    boxes = tf.expand_dims(boxes, axis=0)
    scores = selected_scores
    scores = tf.expand_dims(scores, axis=0)
    classes = tf.gather(classes, selected_indices)
    classes = tf.expand_dims(classes, axis=0)
    valid_detections = num_valid_nms_boxes
    valid_detections = tf.expand_dims(valid_detections, axis=0)

    img = draw_outputs(img, majority_voting((boxes, scores, classes, valid_detections), FLAGS.size, 10), class_names)
    #cv2.imshow('ensemble', img)

    cv2.imwrite('output.jpg', img)






if __name__ == '__main__':
    try:
        app.run(main)
    except SystemExit:
        pass






