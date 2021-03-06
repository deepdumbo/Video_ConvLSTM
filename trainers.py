from util import util
import logging
import tensorflow as tf
import time
import os
from settings import ROOT
import numpy as np


class Trainer:
    def __init__(self,data,model,sess,flags):
        self.data=data
        self.model=model
        self.sess=sess

        # training
        self.lr = flags.lr
        self.lr_decay = flags.lr_decay
        self.lr_decay_epoch = flags.lr_decay_epoch
        self.end_lr = flags.end_lr
        self.batch_size=flags.batch_size
        self.epoch_evaluate=flags.epoch_evaluate
        self.epoch_record=flags.epoch_record
        self.total_loss=0
        self.start_time = time.time()

        self. nbatch=0
        self. total_batch=0

        self.output_dir=flags.output_dir
        self.checkpoint_dir=flags.checkpoint_dir
        self.tf_log_dir=flags.tf_log_dir
        self.save_loss=flags.save_loss
        self.save_weights=flags.save_weights
        self.save_meta_data=flags.save_meta_data

        util.set_logging(flags.log_filename, stream_log_level=logging.INFO, file_log_level=logging.INFO,
                         tf_log_level=tf.logging.WARN)
        logging.info("%s [%s]" % (util.get_now_date(), self.model.name))

        self.build_summary_saver()
        self.init = tf.group(tf.global_variables_initializer(), tf.local_variables_initializer())
        self.sess.run(self.init)


    def train_batch(self):
        feed_dict = {self.model.x:self.data.x[self.nbatch:self.nbatch+8], self.model.y:self.data.y[self.nbatch:self.nbatch+8],self.model.is_training:1,self.model.lr_input:self.lr}
        _, loss = self.sess.run([self.model.training_optimizer, self.model.loss], feed_dict=feed_dict)

        self.total_loss+=loss

    def train(self):
        self.data.load_train()
        self.data.load_test()
        nbatches=self.data.x.shape[0]
        self.total_batch=nbatches//self.batch_size+(0,1)[nbatches%self.batch_size>0]

        # while not(self.nbatch>=self.total_batch or self.lr<self.end_lr):
        while not(self.lr<self.end_lr and self.nbatch>=self.total_batch):
            self.train_batch()
            self.nbatch+=1
            if self.nbatch%self.lr_decay_epoch==0:
                self.lr*=self.lr_decay
            if self.nbatch%self.epoch_evaluate==0:
                loss=self.evaluate()
                self.print_status(loss/self.data.batch_size_test,log=True)
            if self.nbatch%self.epoch_record==0:
                self.test()

        self.test()
        self.save_model()

    def evaluate(self):
        feed_dict = {self.model.x: self.data.x_test,self.model.y:self.data.y_test,self.model.is_training:0}
        loss=self.sess.run(self.model.loss,feed_dict=feed_dict)
        return loss

    def test(self):
        feed_dict = {self.model.x: self.data.x_test,self.model.y:self.data.y_test,self.model.is_training:0}
        y_,loss=self.sess.run((self.model.y_,self.model.loss),feed_dict=feed_dict)
        # print(y_[0,0,:2])
        util.array2image(y_,os.path.join(ROOT,self.output_dir),'predict',self.nbatch)
        util.array2image(self.data.y_test,os.path.join(ROOT,self.output_dir),'truth',self.nbatch)
        logging.info("\n=== [%s] Loss:%f ===" % ( self.data.test_path, loss/self.data.batch_size_test))


    def print_status(self, loss,log=False):
        line_a = "%s Step:%s Loss:%f (Training Loss:%0.3f)" % (
            util.get_now_date(), "{:,}".format(self.nbatch), loss, self.total_loss/(self.nbatch*self.batch_size))
            # util.get_now_date(), "{:,}".format(self.nbatch), loss/self.batch_size, self.total_loss/(self.batch_size*self.nbatch))
        # processing_time = (time.time() - self.start_time) / self.nbatch
        # estimated = processing_time * (self.total_batch - self.nbatch)
        # h = estimated // (60 * 60)
        # estimated -= h * 60 * 60
        # m = estimated // 60
        # s = estimated - m * 60
        # line_b = "Epoch:%d LR:%f (%2.3fsec/step) Estimated:%d:%d:%d" % (
        #     self.nbatch, self.lr, processing_time, h, m, s)
        if log:
            logging.info(line_a)
            # logging.info(line_b)
        # print(line_a)
        # print(line_b)

    def save_model(self, name="", trial=0, log=False):
        if name == "":
            name = self.model.name
        if trial > 0:
            filename = self.checkpoint_dir + "/" + name + "_" + str(trial) + ".ckpt"
        else:
            filename = self.checkpoint_dir + "/" + name + ".ckpt"
        self.saver.save(self.sess, filename)
        if log:
            logging.info("Model saved [%s]." % filename)
        else:
            print("Model saved [%s]." % filename)

    def load_model(self, name="", trial=0, log=False):
        if name == "":
            name = self.model.name
        if trial > 0:
            filename = self.checkpoint_dir + "/" + name + "_" + str(trial) + ".ckpt"
        else:
            filename = self.checkpoint_dir + "/" + name + ".ckpt"
        if not os.path.isfile(filename + ".index"):
            print("Error. [%s] is not exist!" % filename)
            exit(-1)
        self.saver.restore(self.sess, filename)
        if log:
            logging.info("Model restored [ %s ]." % filename)
        else:
            print("Model restored [ %s ]." % filename)

    def build_summary_saver(self):
        if self.save_loss or self.save_weights or self.save_meta_data:
            self.summary_op = tf.summary.merge_all()
            self.train_writer = tf.summary.FileWriter(self.tf_log_dir + "/train")
            self.test_writer = tf.summary.FileWriter(self.tf_log_dir + "/test")

        self.saver = tf.train.Saver(max_to_keep=None)