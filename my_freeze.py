# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
#
# Modifications Copyright 2017 Arm Inc. All Rights Reserved.        
# Added model dimensions as command line argument for generating the pb file
#
#

"""Converts a trained checkpoint into a frozen model for mobile inference.

Once you've trained a model using the `train.py` script, you can use this tool
to convert it into a binary GraphDef file that can be loaded into the Android,
iOS, or Raspberry Pi example code. Here's an example of how to run it:

bazel run tensorflow/examples/speech_commands/freeze -- \
--sample_rate=16000 --dct_coefficient_count=40 --window_size_ms=20 \
--window_stride_ms=10 --clip_duration_ms=1000 \
--model_architecture=conv \
--checkpoint=/tmp/speech_commands_train/conv.ckpt-1300 \
--output_file=/tmp/my_frozen_graph.pb

One thing to watch out for is that you need to pass in the same arguments for
`sample_rate` and other command line variables here as you did for the training
script.

The resulting graph has an input for WAV-encoded data named 'wav_data', one for
raw PCM data (as floats in the range -1.0 to 1.0) called 'decoded_sample_data',
and the output is called 'labels_softmax'.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os.path
import sys

import tensorflow as tf

from tensorflow.contrib.framework.python.ops import audio_ops as contrib_audio
import input_data
import models
from tensorflow.python.framework import graph_util

FLAGS = None


def create_inference_graph(wanted_words, sample_rate, clip_duration_ms,
                           clip_stride_ms, window_size_ms, window_stride_ms,
                           dct_coefficient_count, model_architecture, model_size_info):
  """Creates an audio model with the nodes needed for inference.

  Uses the supplied arguments to create a model, and inserts the input and
  output nodes that are needed to use the graph for inference.

  Args:
    wanted_words: Comma-separated list of the words we're trying to recognize.
    sample_rate: How many samples per second are in the input audio files.
    clip_duration_ms: How many samples to analyze for the audio pattern.
    clip_stride_ms: How often to run recognition. Useful for models with cache.
    window_size_ms: Time slice duration to estimate frequencies from.
    window_stride_ms: How far apart time slices should be.
    dct_coefficient_count: Number of frequency bands to analyze.
    model_architecture: Name of the kind of model to generate.
  """

  words_list = input_data.prepare_words_list(wanted_words.split(','))
  model_settings = models.prepare_model_settings(
      len(words_list), sample_rate, clip_duration_ms, window_size_ms,
      window_stride_ms, dct_coefficient_count)
  runtime_settings = {'clip_stride_ms': clip_stride_ms}
  fingerprint_frequency_size = model_settings['dct_coefficient_count']
  fingerprint_time_size = model_settings['spectrogram_length']
  reshaped_input = tf.placeholder(tf.float32, name='wav_data')

  logits = models.create_model(
      reshaped_input, model_settings, model_architecture, model_size_info,
      is_training=False, runtime_settings=runtime_settings)

  # Create an output to use for inference.
  tf.nn.softmax(logits, name='labels_softmax')


def main(_):

  # Create the model and load its weights.
  sess = tf.InteractiveSession()
  create_inference_graph(FLAGS.wanted_words, FLAGS.sample_rate,
                         FLAGS.clip_duration_ms, FLAGS.clip_stride_ms,
                         FLAGS.window_size_ms, FLAGS.window_stride_ms,
                         FLAGS.dct_coefficient_count, FLAGS.model_architecture,
                         FLAGS.model_size_info)
  models.load_variables_from_checkpoint(sess, FLAGS.checkpoint)

  # Turn all the variables into inline constants inside the graph and save it.
  frozen_graph_def = graph_util.convert_variables_to_constants(
      sess, sess.graph_def, ['labels_softmax'])
  tf.train.write_graph(
      frozen_graph_def,
      os.path.dirname(FLAGS.output_file),
      os.path.basename(FLAGS.output_file),
      as_text=False)
  tf.logging.info('Saved frozen graph to %s', FLAGS.output_file)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--sample_rate',
      type=int,
      default=16000,
      help='Expected sample rate of the wavs',)
  parser.add_argument(
      '--clip_duration_ms',
      type=int,
      default=1000,
      help='Expected duration in milliseconds of the wavs',)
  parser.add_argument(
      '--clip_stride_ms',
      type=int,
      default=30,
      help='How often to run recognition. Useful for models with cache.',)
  parser.add_argument(
      '--window_size_ms',
      type=float,
      default=30.0,
      help='How long each spectrogram timeslice is',)
  parser.add_argument(
      '--window_stride_ms',
      type=float,
      default=10.0,
      help='How long the stride is between spectrogram timeslices',)
  parser.add_argument(
      '--dct_coefficient_count',
      type=int,
      default=40,
      help='How many bins to use for the MFCC fingerprint',)
  parser.add_argument(
      '--checkpoint',
      type=str,
      default='',
      help='If specified, restore this pretrained model before any training.')
  parser.add_argument(
      '--model_architecture',
      type=str,
      default='dnn',
      help='What model architecture to use')
  parser.add_argument(
      '--model_size_info',
      type=int,
      nargs="+",
      default=[128,128,128],
      help='Model dimensions - different for various models')
  parser.add_argument(
      '--wanted_words',
      type=str,
      default='yes,no,up,down,left,right,on,off,stop,go',
      help='Words to use (others will be added to an unknown label)',)
  parser.add_argument(
      '--output_file', type=str, help='Where to save the frozen graph.')
  FLAGS, unparsed = parser.parse_known_args()
  tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
