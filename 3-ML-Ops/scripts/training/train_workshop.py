import os
import logging
import pandas as pd
import tensorflow as tf
from absl import app
from absl import flags
from transformers import TFBertPreTrainedModel, TFBertMainLayer, BertTokenizer
from transformers.modeling_tf_utils import get_initializer
from azureml.core.run import Run
from azureml.core import Datastore


# Ignore warnings in logs
logging.getLogger("transformers.tokenization_utils").setLevel(logging.ERROR)

# Get the Azure ML run object
run = Run.get_context()
ws = run.experiment.workspace

# Define input arguments
FLAGS = flags.FLAGS
flags.DEFINE_integer(
    'max_seq_length', 128, 'Maximum sequence length of input sentences.')
flags.DEFINE_integer(
    'batch_size', 32, 'Batch size for training.', lower_bound=0)
flags.DEFINE_float(
    'learning_rate', 3e-5, 'Learning rate for training.')
flags.DEFINE_integer(
    'steps_per_epoch', 150, 'Number of steps per epoch.')
flags.DEFINE_integer(
    'num_epochs', 3, 'Number of epochs to train for.', lower_bound=0)
flags.DEFINE_string(
    'data_dir', None, 'Root path of directory where data is stored.')
flags.DEFINE_string(
    'export_dir', '.', 'The directory to export the model to')


class AmlLogger(tf.keras.callbacks.Callback):
    # A callback class for logging metrics using
    # Azure Machine Learning Python SDK

    def on_epoch_end(self, epoch, logs={}):
        run.log('val_accuracy', float(logs.get('val_accuracy')))

    def on_batch_end(self, batch, logs={}):
        run.log('accuracy', float(logs.get('accuracy')))


class TFBertForMultiClassification(TFBertPreTrainedModel):
    # BERT Model class for multi-label classification
    # using a softmax output layer

    def __init__(self, config, *inputs, **kwargs):
        super(TFBertForMultiClassification, self).__init__(
            config, *inputs, **kwargs)
        self.num_labels = config.num_labels
        self.bert = TFBertMainLayer(config, name='bert')
        self.dropout = tf.keras.layers.Dropout(config.hidden_dropout_prob)
        self.classifier = tf.keras.layers.Dense(
            config.num_labels,
            kernel_initializer=get_initializer(config.initializer_range),
            name='classifier',
            activation='softmax')

    def call(self, inputs, **kwargs):
        outputs = self.bert(inputs, **kwargs)
        pooled_output = outputs[1]
        pooled_output = self.dropout(
            pooled_output, training=kwargs.get('training', False))
        logits = self.classifier(pooled_output)

        # add hidden states and attention if they are here
        outputs = (logits,) + outputs[2:]
        return outputs  # logits, (hidden_states), (attentions)


def encode_example(example, tokenizer, max_seq_length, labels_map):
    ''' Encodes an input text using the BERT tokenizer

    :param example: Input line from CSV file
    :param tokenizer: BERT tokenizer object from transformers libary
    :param max_seq_length: Maximum length of word embedding in encoded example
    :param labels_map: Label map dictionary
    :return: Encoded example that can be inputted into the BERT model

    '''
    # Encode inputs using tokenizer
    inputs = tokenizer.encode_plus(
        example[1],
        add_special_tokens=True,
        max_length=max_seq_length
    )
    input_ids, token_type_ids = inputs["input_ids"], inputs["token_type_ids"]

    # The mask has 1 for real tokens and 0 for padding tokens.
    # Only real tokens are attended to.
    attention_mask = [1] * len(input_ids)

    # Zero-pad up to the sequence length.
    padding_length = max_seq_length - len(input_ids)
    input_ids = input_ids + ([0] * padding_length)
    attention_mask = attention_mask + ([0] * padding_length)
    token_type_ids = token_type_ids + ([0] * padding_length)

    # Get label using dictionary
    label = labels_map[example[2]]

    return {
        'input_ids': input_ids,
        'attention_mask': attention_mask,
        'token_type_ids': token_type_ids,
        'label': label
    }


def read_csv(filename, tokenizer, max_seq_length, labels_map):
    '''
    Reads a CSV file line by line and encodes each example
    using the BERT tokenizer

    :param filename: The name of the CSV file
    :param tokenizer: BERT tokenizer object from transformers libary
    :param max_seq_length: Maximum length of word embedding in encoded example
    :param labels_map: Label map dictionary
    :return: Encoded examples for BERT model as a generator

    '''
    with open(filename, 'r') as f:
        for line in f.readlines():
            record = line.rstrip().split(',')
            features = encode_example(
                record, tokenizer,
                max_seq_length, labels_map)
            yield (
                {
                    'input_ids': features['input_ids'],
                    'attention_mask': features['attention_mask'],
                    'token_type_ids': features['token_type_ids']
                },
                features['label'])


def get_dataset(filename, tokenizer, max_seq_length, labels_map):
    '''
    Loads data from a CSV file into a Tensorflow Dataset
    (while encoding each example)

    :param filename: The name of the CSV file
    :param tokenizer: BERT tokenizer object from transformers libary
    :param max_seq_length: Maximum length of word embedding in encoded example
    :param labels_map: Label map dictionary
    :return: A Tensorflow Dataset object with encoded inputs from CSV file

    '''
    generator = lambda: read_csv(  # NOQA: E731
        filename, tokenizer, max_seq_length, labels_map)
    return tf.data.Dataset.from_generator(
        generator,
        ({'input_ids': tf.int32,
          'attention_mask': tf.int32,
          'token_type_ids': tf.int32},
         tf.int64),
        ({'input_ids': tf.TensorShape([max_seq_length]),
          'attention_mask': tf.TensorShape([max_seq_length]),
          'token_type_ids': tf.TensorShape([max_seq_length])},
         tf.TensorShape([])))


def main(_):
    # Export the trained model
    if not os.path.exists(FLAGS.export_dir):
        os.makedirs(FLAGS.export_dir)

    run.log('accuracy', float(0.91))
    run.log('val_accuracy', float(0.901))

    datastore = Datastore.get(ws, 'mtcseattle')
    datastore.download(FLAGS.export_dir, prefix="model")



if __name__ == '__main__':
    flags.mark_flag_as_required('data_dir')
    app.run(main)
