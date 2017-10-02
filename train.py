import numpy as np
import sys
import math
import operator
import csv
import glob,os
import xlrd
import cv2
import pandas as pd

from sklearn.svm import SVC
from collections import Counter
from sklearn.metrics import confusion_matrix
import scipy.io as sio

from keras.models import Sequential
from keras.layers import LSTM, Dense, TimeDistributed
from keras.utils import np_utils
from keras import metrics
from keras import backend as K
from keras.models import model_from_json
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.preprocessing.sequence import pad_sequences
import keras

from labelling import collectinglabel
from reordering import readinput
from evaluationmatrix import fpr
from utilities import Read_Input_Images, get_subfolders_num, data_loader_with_LOSO, label_matching


############## Path Preparation ######################
dB = "CASME2_TIM"
workplace = '/media/ice/OS/Datasets/' + dB + "/"
inputDir = '/media/ice/OS/Datasets/' + dB + "/" + dB + "/" 
######################################################

############# Reading Labels from XCEL ########################
wb=xlrd.open_workbook('/media/ice/OS/Datasets/CASME2_label_Ver_2.xls')
ws=wb.sheet_by_index(0)    
colm=ws.col_slice(colx=0,start_rowx=1,end_rowx=None)
iD=[str(x.value) for x in colm]
colm=ws.col_slice(colx=1,start_rowx=1,end_rowx=None)
vidName=[str(x.value) for x in colm]
colm=ws.col_slice(colx=6,start_rowx=1,end_rowx=None)
expression=[str(x.value) for x in colm]
table=np.transpose(np.array([np.array(iD),np.array(vidName),np.array(expression)],dtype=str))
# print(table)
###############################################################



###################### Samples to-be ignored ##########################
# ignored due to:
# 1) no matching label.
# 2) fear, sadness are excluded due to too little data, see CASME2 paper for more
IgnoredSamples = ['sub09/EP13_02/','sub09/EP02_02f/','sub10/EP13_01/','sub17/EP15_01/',
					'sub17/EP15_03/','sub19/EP19_04/','sub24/EP10_03/','sub24/EP07_01/',
					'sub24/EP07_04f/','sub24/EP02_07/','sub26/EP15_01/']
listOfIgnoredSamples=[]
for s in range(len(IgnoredSamples)):
	if s==0:
		listOfIgnoredSamples=[inputDir+IgnoredSamples[s]]
	else:
		listOfIgnoredSamples.append(inputDir+IgnoredSamples[s])
### Get index of samples to be ignored in terms of subject id ###
IgnoredSamples_index = np.empty([0])
for item in IgnoredSamples:
	item = item.split('sub', 1)[1]
	item = int(item.split('/', 1)[0]) - 1 
	IgnoredSamples_index = np.append(IgnoredSamples_index, item)

#######################################################################

############## Variables ###################
r=50; w=50
resizedFlag=1
subjects=26
samples=246
n_exp=5
VidPerSubject = get_subfolders_num(inputDir, IgnoredSamples_index)
timesteps_TIM = 10
data_dim = r * w
pad_sequence = 10
############################################

################## Clearing labels.txt ################
os.remove(workplace + "Classification/CASME2_TIM_label.txt")
#######################################################

############ Reading Images and Labels ################
SubperdB = Read_Input_Images(inputDir, listOfIgnoredSamples, dB, resizedFlag, table, workplace)
print("Loaded Images into the tray...")
labelperSub = label_matching(workplace, dB, subjects, VidPerSubject)
print("Loaded Labels into the tray...")
#######################################################


########### Model #######################
model = Sequential()
model.add(Conv2D( 32, kernel_size=(1, 1), strides=(1,1), input_shape=(50, 50, 1) ))
model.add(MaxPooling2D(pool_size=3, strides=2))
model.add(Conv2D( 64, kernel_size=(1, 1), activation='relu'))
model.add(MaxPooling2D(pool_size=3, strides=2))
model.add(Conv2D( 64, kernel_size=(1, 1), activation='relu'))
model.add(MaxPooling2D(pool_size=3, strides=2))
model.add(Dense( 512, activation='relu'))
model.add(Dense( 512, activation='relu'))
model.add(Flatten())
model.add(Dense( 5, activation='softmax'))
model.compile(loss='mean_absolute_error',optimizer='Adam',metrics=[metrics.categorical_accuracy])


temporal_model = Sequential()
temporal_model.add(LSTM(512, return_sequences=True, input_shape=(5, pad_sequence)))
temporal_model.add(LSTM(512, return_sequences=False))
temporal_model.add(Dense(128, activation='sigmoid'))
temporal_model.add(Dense(5, activation='sigmoid'))
temporal_model.compile(loss='categorical_crossentropy', optimizer='Adam', metrics=[metrics.categorical_accuracy])
#########################################

########### Training Process ############
# Todo:
# 1) LOSO (done)
# 2) call model (done)
# 3) saving model architecture
# 4) Saving Checkpoint
# 5) make prediction (done)

for sub in range(subjects):
	image_label_mapping = np.empty([0])

	Train_X, Train_Y, Test_X, Test_Y = data_loader_with_LOSO(sub, SubperdB, labelperSub, subjects)
	
	# Rearrange Training labels into a vector of images, breaking sequence
	Train_X_spatial = Train_X.reshape(Train_X.shape[0]*10, r, w, 1)
	Test_X_spatial = Test_X.reshape(Test_X.shape[0]* 10, r, w, 1)

	# Extend Y labels 10 fold, so that all images have labels
	Train_Y_spatial = np.repeat(Train_Y, 10)
	Train_Y_spatial = Train_Y_spatial.reshape(int(Train_Y_spatial.shape[0]/5), 5)
	Test_Y_spatial = np.repeat(Test_Y, 10)
	Test_Y_spatial = Test_Y_spatial.reshape(int(Test_Y_spatial.shape[0]/5), 5)

	print ("Train_X_shape: " + str(np.shape(Train_X_spatial)))
	print ("Train_Y_shape: " + str(np.shape(Train_Y_spatial)))
	print ("Test_X_shape: " + str(np.shape(Test_X_spatial)))	
	print ("Test_Y_shape: " + str(np.shape(Test_Y_spatial)))	
	
	############ Spatial Encoder ###############
	output = model.fit(Train_X_spatial, Train_Y_spatial, batch_size=32, epochs=1, validation_split=0.05, shuffle=True )
	features = model.predict(Train_X_spatial)
	############################################


	# features = model.predict(Train_X)
	print(features.shape)
	features = features.reshape(10, int(features.shape[0]/10), features.shape[1])
	print(features.shape)
	# features = pad_sequences(features, maxlen=pad_sequence)
	features = features.reshape(features.shape[1], features.shape[2], features.shape[0])
	print(features.shape)
	temporal_model.fit(features, Train_Y, batch_size = 10, epochs=1)


	# print(output.values)
	# output2 = temporal_model.fit(output, batch_size=10, epochs=1, validation_split=0.05)
	# score, acc = model.evaluate(Test_X, Test_Y, batch_size=10)
