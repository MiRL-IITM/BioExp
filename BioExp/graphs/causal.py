import matplotlib
matplotlib.use('Agg')
import keras
import numpy as np
import tensorflow as tf
import os
import pdb
import cv2 
import pickle
from matplotlib import pyplot as plt
import matplotlib.gridspec as gridspec


import pandas as pd
from ..helpers.utils import *
from ..spatial.ablation import Ablate

from keras.models import Model
from keras.utils import np_utils
from tqdm import tqdm
from skimage.transform import resize as imresize

from scipy.ndimage.measurements import label
from scipy.ndimage.morphology import binary_dilation, generate_binary_structure


class CausalGraph():
	"""
		class to generate causal 
	"""
	def __init__(self, model, weights_pth, metric, layer_names, max_clusters = None, classinfo=None):
		
		"""
			model       : keras model architecture (keras.models.Model)
			weights_pth : saved weights path (str)
			metric      : metric to compare prediction with gt, for example dice, CE
			layer_name  : name of the layer which needs to be ablated
			test_img    : test image used for ablation
			max_clusters: maximum number of clusters per layer
		"""     

		self.model      = model
		self.modelcopy  = keras.models.clone_model(self.model)
		self.weights    = weights_pth
		self.layers     = layer_names
		self.metric     = metric
		self.classinfo  = classinfo
		self.noutputs   = len(self.model.outputs)

	def get_layer_idx(self, layer_name):
		for idx, layer in enumerate(self.model.layers):
			if layer.name == layer_name:
				return idx
		

	def get_link(self, nodeA_info, nodeB_info, dataset_path, loader, save_path, max_samples = 1):
		"""
			get link between two nodes, nodeA, nodeB
			occlude at nodeA and observe changes in nodeB
			nodeA_info    : {'layer_name', 'layer_idxs'}
			nodeB_info    : {'layer_name', 'layer_idxs'}
		"""
		self.modelcopy.load_weights(self.weights, by_name = True)
		self.model.load_weights(self.weights, by_name = True)

		nodeA_idx   = self.get_layer_idx(nodeA_info['layer_name'])
		nodeA_idxs  = nodeA_info['layer_idxs']

		nodeB_idx   = self.get_layer_idx(nodeB_info['layer_name'])
		nodeB_idxs  = nodeB_info['layer_idxs']


		layer_weights = np.array(self.modelcopy.layers[nodeA_idx].get_weights())
		occluded_weights = layer_weights.copy()
		for j in nodeA_idxs:
			occluded_weights[0][:,:,:,j] = 0
			occluded_weights[1][j] = 0
		self.modelcopy.layers[nodeA_idx].set_weights(occluded_weights)

		layer_weights = np.array(self.modelcopy.layers[nodeB_idx].get_weights())
		occluded_weights = layer_weights.copy()

		for j in nodeB_idxs:
			occluded_weights[0][:,:,:,j] = 0
			occluded_weights[1][j] = 0
		self.modelcopy.layers[nodeB_idx].set_weights(occluded_weights)

		dice_json = {}
		for class_ in self.classinfo.keys():
			dice_json[class_] = []

		input_paths = os.listdir(dataset_path)
		for i in range(len(input_paths) if len(input_paths) < max_samples else max_samples):
			input_, label_ = loader(os.path.join(dataset_path, input_paths[i]), 
								os.path.join(dataset_path, 
								input_paths[i]).replace('mask', 'label').replace('labels', 'masks'))
			prediction_occluded = np.squeeze(self.modelcopy.predict(input_[None, ...]))
			prediction = np.squeeze(self.model.predict(input_[None, ...]))

			idx = 0
			if self.noutputs > 1:
				for ii in range(self.noutputs):
					if prediction[ii] == self.nclasses:
						idx = ii 
						break;


			for class_ in self.classinfo.keys():
				if self.noutputs > 1:
					dice_json[class_].append(self.metric(label_, prediction[idx].argmax(axis = -1), self.classinfo[class_]) - 
								self.metric(label_, prediction_occluded[idx].argmax(axis = -1), self.classinfo[class_]))
				else:
					dice_json[class_].append(self.metric(label_, prediction.argmax(axis = -1), self.classinfo[class_]) - 
								self.metric(label_, prediction_occluded.argmax(axis = -1), self.classinfo[class_]))


		for class_ in self.classinfo.keys():
			dice_json[class_] = np.mean(dice_json[class_])

		return dice_json


	def generate_graph(self, graph_info):
		pass

	def perform_intervention(self
