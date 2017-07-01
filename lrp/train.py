from . import modules
from . import utils
import numpy as np 
import tensorflow as tf

def weight_variable(shape):
	try: s = shape[0].as_list(); shape = s[1:] + shape[1:]
	except: pass
	return tf.Variable(tf.truncated_normal(shape, stddev=0.1))

def bias_variable(shape): return tf.Variable(tf.constant(0.1, shape=shape))

def shape(T):
	if isinstance(T, tf.Tensor): return [-1 if d is None else d for d in T.get_shape().as_list()]
	return [-1 if d is None else d for d in T.shape]

def expand_dims(A, axes=[]):
	for axis in axes:
		A = tf.expand_dims(A, axis=axis)
	return A

def tensordot(A, B, axes):
	# Because tf.tensordot fucks with the shape
	new_len = len(shape(A))+len(shape(B))-axes
	A_ = expand_dims(A, axes=range(len(shape(A)),new_len))
	B_ = expand_dims(B, axes=range(new_len-len(shape(B))))
	reduce_axis = list(range(len(shape(A))-axes, len(shape(A))))
	return tf.reduce_sum(tf.multiply(A_, B_), axis=reduce_axis)

# -------------------------
# Network
# -------------------------
class Network():
	def __init__(self, layers, input_tensor, y_):
		self.layers = layers
		self.input_tensor = input_tensor
		self.y_ = y_
		self.session = None

		# forward through every layer
		activation = input_tensor
		print("Network layer mappings:", activation.shape)

		for layer in self.layers:
			activation = layer.forward(activation)
			print("->", activation.shape)

		self.y = activation

		self.accuracy = tf.reduce_mean(tf.cast(tf.equal(tf.argmax(self.y, 1), tf.argmax(self.y_, 1)), tf.float32))
		self.loss = tf.nn.sigmoid_cross_entropy_with_logits(labels=self.y_, logits=self.y)
		self.train = tf.train.AdamOptimizer().minimize(self.loss)
		self.saver = tf.train.Saver()

	def deep_taylor(self, class_filter): # class_filter: tf.constant one hot-vector
		R = tf.multiply(self.y, class_filter)
		print("DEEP TAYLOR *_*")
		print(R.get_shape().as_list())
			
		for l in self.layers[::-1][:-1]:
			print(type(l))
			R = l.deep_taylor(R)
			print(" -> ", R.get_shape().as_list())
		return R

	def mixed_lrp(self, class_filter, methods = "simple"): # class_filter: tf.constant one hot-vector
		"""
		Methods: which method to use?
				If the same method should be used for every layer, then the string can be passed: ("simple" / "ab")
				If this is the case, but the methods needs an additional numeric parameter, then it can be passed like ["methodstr", <param>]
				If the methods shall be specified for each layer, then a list has to be passed, where each element is a list like ["methodstr"(, <param>)]
		"""

		R = tf.multiply(self.y, class_filter)
		print("\nLayerwise Relevance Propagation <3")
		if isinstance(methods, str):
			methods = [[methods]] * (len(self.layers)-1)
		if isinstance(methods[1], (float, int)):
			methods = [methods] * (len(self.layers)-1)

		for l, m in zip(self.layers[::-1][:-1], methods[::-1]):
			print(type(l), ": ", m)
			if m[0] == "deep_taylor":
				R = l.deep_taylor(R)
			elif m[0] == "simple":
				R = l.simple_lrp(R)
			elif m[0] == "ab" or m[0] == "alphabeta":
				if len(m)>1:
					R = l.alphabeta_lrp(R, m[1])
				else:
					R = l.alphabeta_lrp(R)
			elif m[0] == "simpleb":
				R = l.simple_lrp(R)
			elif m[0] == "abb" or m[0] == "alphabeta":
				R = l.alphabeta_lrp(R, m[1])
			else:
				raise Exception("Unknown LRP method: {}".format(m[0]))
		return R	

	def save_params(self, export_dir):
		tf.gfile.MakeDirs(export_dir)
		save_path = self.saver.save(self.sess, "{}/model.ckpt".format(export_dir))
		print("Saved model to ", save_path)

	def load_params(self, import_dir):
		self.saver.restore(self.sess, "{}/model.ckpt".format(import_dir))

	def close_sess(self):
		try: self.sess.close()
		except: pass

	def create_session(self):
		self.close_sess()
		self.set_session(tf.Session())
		self.sess.run(tf.global_variables_initializer())
		return self.sess

	def set_session(self, sess):
		self.sess = sess
		for layer in self.layers:
			layer.set_session(sess)

	def to_numpy(self):	
		# extract Parameters, and return a modules.network
		lrp_layers = []
		for layer in self.layers:
			lrp_layers.append(layer.to_numpy())
		return modules.Network(lrp_layers)

	def __lrp_forward(self, X):
		lrp_network = self.to_numpy()
		activation_tensors = [layer.input_tensor for layer in self.layers[1:]] + [self.layers[-1].output_tensor] # actiovation[0] is formated input, serves as input for layer 0 of numpy network
		activation = self.sess.run(activation_tensors, feed_dict={self.input_tensor: X})
		for i in range(len(self.layers)-1):
			np_activation = np.reshape(lrp_network.layers[i].forward(activation[i]), activation[i+1].shape) # np forwards the tf activation, so a defect early layer will be detected, but the later layers can still pass the test
		return lrp_network, np_activation

	def __get_numpy_deeptaylor(self, X, dim): # dim: one hot vector; heatmaps for correct class: dim = y_
		# X: either np.array or tf.Tensor
		lrp_network, y = self.lrp_forward(X)
		return lrp_network.relprop(y*dim), y*dim

	def get_numpy_deeptaylor(self, X, dim): # dim: one hot vector; heatmaps for correct class: dim = y_
		# X: either np.array or tf.Tensor
		numpy_network = self.to_numpy()
		y = numpy_network.forward(X)
		return numpy_network.relprop(y*dim), y*dim

	def conservation_check(self, heatmaps, R):
		# input as numpy.array
		num_samples = heatmaps.shape[0]
		h = np.reshape(heatmaps, [num_samples, np.prod(heatmaps.shape[1:])])
		hR = np.sum(h, axis=1)
		R = np.reshape(R, hR.shape)
		err = np.absolute(hR-R)
		print("Relevance - Sum(heatmap) = ", err)

	def simple_test(self, feed_dict):
		Conservation = [l.conservation for l in self.layers[::-1][1:] if isinstance(l, (Linear, Convolution, Pooling))]
		Layerwise_R = [l.R_simple for l in self.layers[::-1][1:] if isinstance(l, (Linear, Convolution, Pooling))]
		test_layers = [l for l in self.layers[::-1][1:] if isinstance(l, (Linear, Convolution, Pooling))]
		conservation, layerwise_r = self.sess.run([Conservation, Layerwise_R], feed_dict=feed_dict)

		for c, r, l in zip(conservation, layerwise_r, test_layers):
			print(type(l))
			print("Conservation :", c)
			#print("share.sum(axis=1) :", np.sum(s, axis=1))
			input()

	def ab_test(self, feed_dict):
		ab_errors = self.sess.run([l.ab_forward_error for l in self.layers if isinstance(l, Convolution)], feed_dict=feed_dict)
		for error in ab_errors:
			print("AB forward error: ", np.mean(np.absolute(error))); input()

	def layerwise_tfnp_test(self, X, T):
		np_nn = self.to_numpy()
		cnn_layer_tensors = [layer.output_tensor for layer in self.layers]
		cnn_layer_activations = self.sess.run(cnn_layer_tensors, feed_dict=self.feed_dict([X, T]))
		a = X
		for l, a_ in zip(np_nn.layers, cnn_layer_activations):
			a = l.forward(a)
			np.testing.assert_allclose(a, a_, atol=1e-5)
		print("All np/tf layers do the same :) ")
		
	def feed_dict(self, batch):
		return {self.input_tensor: batch[0], self.y_: batch[1]}

# -------------------------
# Abstract Layer
# -------------------------
class Layer():
	def __init__(self):
		self.sess = None

	def set_session(self, sess):
		self.sess = sess

	def to_numpy(self):		# For layers with weights and biases (Linear, Convolution); Pooling and ReLU override this
		if self.sess is None:
			raise Exception("Trying to extract variables without active session")
		else:
			W, B = self.sess.run([self.weights, self.biases], feed_dict={})
			return self.lrp_module(W, B)

# -------------------------
# Format Layer
# -------------------------
class Format(Layer):
	def forward(self, input_tensor):
		self.input_tensor = input_tensor
		self.output_tensor = tf.add(input_tensor*(utils.highest-utils.lowest), utils.lowest)
		return self.output_tensor

	def to_numpy(self):
		return modules.Format()

class Flatten(Layer):
	def forward(self, input_tensor):
		self.input_tensor = input_tensor
		self.output_tensor = tf.reshape(input_tensor, [-1, np.prod(shape(input_tensor)[1:])])
		return self.output_tensor

# -------------------------
# Activation Layers
# -------------------------
class Activation(Layer):
	def deep_taylor(self, R): return R
	def simple_lrp(self, R): return R
	def alphabeta_lrp(self, R, alpha=1.): return R

class ReLU(Activation):
	def forward(self, input_tensor):
		self.input_tensor = input_tensor
		self.output_tensor = tf.nn.relu(input_tensor)
		return self.output_tensor

	def to_numpy(self):
		return modules.ReLU()

class Tanh(Activation):
	def forward(self, input_tensor):
		self.input_tensor = input_tensor
		self.output_tensor = tf.nn.tanh(input_tensor)
		return self.output_tensor

class Abs(Activation):
	def forward(self, input_tensor):
		self.input_tensor = input_tensor
		self.output_tensor = tf.abs(input_tensor)
		return self.output_tensor

	def to_numpy(self):
		return modules.Abs()

# -------------------------
# Fully-connected layer
# -------------------------
class Linear(Layer):
	def __init__(self, num_neurons):
		super().__init__()
		self.output_dims = num_neurons

	def forward(self, input_tensor):
		input_shape = input_tensor.get_shape().as_list()
		if len(input_shape) == 4:
			input_shape = [-1, np.prod(input_shape[1:])]
			input_tensor = tf.reshape(input_tensor, input_shape)
		self.input_tensor = input_tensor
		self.weights = weight_variable([input_tensor.shape, self.output_dims])
		self.biases = bias_variable([self.output_dims])
		self.activators = tf.matmul(self.input_tensor, self.weights)
		self.output_tensor = self.activators + self.biases
		return self.output_tensor

	def simple_bias_lrp(self, R):
		# calculate activators = input_tensor*weights, but also each summand
		input_ = tf.reshape(self.input_tensor, shape(self.input_tensor)+[1])
		weights_ = tf.expand_dims(self.weights, axis=0)
		activators_ = tf.multiply(input_, weights_) + tf.divide(tf.expand_dims(self.biases, axis=0), shape(input_)[1]) #shape: [batch_size, input_dims, output_dims] | [i,j,h] -> input[i,j]*weights[j,h]
		activators = tf.reduce_sum(activators_, axis=1) #[i,j] -> input[i].dot(weights[:,h])
		# normalize a_ axis 1
		activator_share = tf.divide(activators_, tf.expand_dims(activators, axis=1)) #-> [i,j,h] -> input[i,j]*weights[j,h]/input[i].dot(weights[:,h])
		R_ = tf.expand_dims(R, axis=1) #[None, 1, j]: input relevance j
		R_out_ = tf.multiply(R_, activator_share)		#[None, i, j]: R_in[j]/a_[,i,j]
		R_out = tf.reduce_sum(R_out_, axis=2)

		#self.conservation = tf.reduce_sum(R) / tf.reduce_sum(R_out)
		return R_out

	def simple_lrp(self, R):
		R = tf.reshape(R, shape(self.output_tensor))
		R_per_act = tf.divide(R, self.activators+1e-9)
		R_per_in_act = tf.gradients(self.activators, self.input_tensor, grad_ys=R_per_act)[0]
		R_out = tf.multiply(R_per_in_act, self.input_tensor)
		self.R_simple = R_out
		self.conservation = tf.reduce_sum(R) / tf.reduce_sum(R_out)
		return R_out

	def simple_lrp_(self, R):
		# calculate activators = input_tensor*weights, but also each summand
		input_ = tf.reshape(self.input_tensor, shape(self.input_tensor)+[1])
		weights_ = tf.expand_dims(self.weights, axis=0)
		activators_ = tf.multiply(input_, weights_) #shape: [batch_size, input_dims, output_dims] | [i,j,h] -> input[i,j]*weights[j,h]
		activators = tf.reduce_sum(activators_, axis=1) #[i,j] -> input[i].dot(weights[:,h])
		# normalize a_ axis 1
		activator_share = tf.divide(activators_, tf.expand_dims(activators, axis=1)) #-> [i,j,h] -> input[i,j]*weights[j,h]/input[i].dot(weights[:,h])
		R_ = tf.expand_dims(R, axis=1) #[None, 1, j]: input relevance j
		R_out_ = tf.multiply(R_, activator_share)		#[None, i, j]: R_in[j]/a_[,i,j]
		R_out = tf.reduce_sum(R_out_, axis=2)

		self.R_simple = R_out
		self.conservation = tf.reduce_sum(R) / tf.reduce_sum(R_out)
		return R_out

	def alphabeta_lrp(self, R, alpha=1.):
		input_ = tf.reshape(self.input_tensor, shape(self.input_tensor)+[1])
		weights_ = tf.expand_dims(self.weights, axis=0)
		activators_ = tf.multiply(input_, weights_) #shape: [batch_size, input_dims, output_dims] | [i,j,h] -> input[i,j]*weights[j,h]
		
		activators_plus_ = tf.nn.relu(activators_)
		activators_plus = tf.reduce_sum(activators_plus_, axis=1) #[i,j] -> input[i].dot(weights[:,h])
		# normalize a_ axis 1
		activators_plus_share = tf.divide(activators_plus_, tf.expand_dims(activators_plus, axis=1)) #-> [i,j,h] -> input[i,j]*weights[j,h]/input[i].dot(weights[:,h])
		R_ = tf.expand_dims(R, axis=1)
		R_plus_out_ = tf.multiply(R_, activators_plus_share)		#[None, i, j]: R_in[j]/a_[,i,j]
		R_plus_out = tf.reduce_sum(R_plus_out_, axis=2)

		activators_minus_ = tf.nn.relu(-activators_)
		activators_minus = tf.reduce_sum(activators_minus_, axis=1) #[i,j] -> input[i].dot(weights[:,h])
		# normalize a_ axis 1
		activators_minus_share = tf.divide(activators_minus_, tf.expand_dims(activators_minus, axis=1)) #-> [i,j,h] -> input[i,j]*weights[j,h]/input[i].dot(weights[:,h])
		R_minus_out_ = tf.multiply(R_, activators_minus_share)		#[None, i, j]: R_in[j]/a_[,i,j]
		R_minus_out = tf.reduce_sum(R_minus_out_, axis=2)

		R_out = alpha*R_plus_out + (1.-alpha)*R_minus_out
		return R_out

	def alphabeta_lrp_bias(self, R, alpha=1.):
		def shape(T): return [-1 if d is None else d for d in T.get_shape().as_list()]

		input_ = tf.reshape(self.input_tensor, shape(self.input_tensor)+[1])
		weights_ = tf.expand_dims(self.weights, axis=0)
		activators_ = tf.multiply(input_, weights_) + tf.divide(tf.expand_dims(self.biases, axis=0), shape(input_)[1]) #shape: [batch_size, input_dims, output_dims] | [i,j,h] -> input[i,j]*weights[j,h]
		
		activators_plus_ = tf.nn.relu(activators_)
		activators_plus = tf.reduce_sum(activators_plus_, axis=1) #[i,j] -> input[i].dot(weights[:,h])
		# normalize a_ axis 1
		activators_plus_share = tf.divide(activators_plus_, tf.expand_dims(activators_plus, axis=1)) #-> [i,j,h] -> input[i,j]*weights[j,h]/input[i].dot(weights[:,h])
		R_ = tf.expand_dims(R, axis=1)
		R_plus_out_ = tf.multiply(R_, activators_plus_share)		#[None, i, j]: R_in[j]/a_[,i,j]
		R_plus_out = tf.reduce_sum(R_plus_out_, axis=2)

		activators_minus_ = tf.nn.relu(-activators_)
		activators_minus = tf.reduce_sum(activators_minus_, axis=1) #[i,j] -> input[i].dot(weights[:,h])
		# normalize a_ axis 1
		activators_minus_share = tf.divide(activators_minus_, tf.expand_dims(activators_minus, axis=1)) #-> [i,j,h] -> input[i,j]*weights[j,h]/input[i].dot(weights[:,h])
		R_minus_out_ = tf.multiply(R_, activators_minus_share)		#[None, i, j]: R_in[j]/a_[,i,j]
		R_minus_out = tf.reduce_sum(R_minus_out_, axis=2)

		R_out = alpha*R_plus_out + (1.-alpha)*R_minus_out
		return R_out

class NextLinear(Linear):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.lrp_module = modules.NextLinear

	def deep_taylor(self, R):
		self.R_in = R
		V = tf.nn.relu(self.weights)
		Z = tf.matmul(self.input_tensor, V) + 1e-9
		S = tf.divide(R, Z)
		C = tf.matmul(S, tf.transpose(V))
		self.R_out = tf.multiply(self.input_tensor, C)
		return self.R_out

class FirstLinear(Linear):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.lrp_module = modules.FirstLinear

	def deep_taylor(self, R):
		self.R_in = R
		W,V,U = self.weights, tf.maximum(0.,self.weights), tf.minimum(0.,self.weights)
		X,L,H = self.input_tensor, self.input_tensor*0 + utils.lowest, self.input_tensor*0 + utils.highest

		Z = tf.matmul(X,W)-tf.matmul(L,V)-tf.matmul(H,U)+1e-9
		S = tf.divide(R,Z)
		self.R_out = X*tf.matmul(S,tf.transpose(W))-tf.multiply(L,tf.matmul(S,tf.transpose(V))) - tf.multiply(H, tf.matmul(S,tf.transpose(U)))
		return self.R_out

# -------------------------
# Sum-pooling layer
# -------------------------
class Pooling(Layer):
	def forward(self, input_tensor):
		input_shape = input_tensor.get_shape().as_list()[1:3]
		if input_shape[0] % 2 + input_shape[1] % 2 > 0:
			raise Exception("Input for pooling layer must have even spatial dims, but has "+str(input_shape))
		self.input_tensor = input_tensor
		# alternative implementation for:
		output_tensor = tf.nn.pool(input_tensor, [2, 2], "AVG", "VALID", strides=[2,2])*2
		# using the form output = tensordor(input, weights)
		"""
		_, h, w, c = self.input_tensor.shape
		h, w, c = int(h), int(w), int(c)
		weights = np.zeros([h, w, int(h/2), int(w/2)], dtype=np.float32)
		for i,j in [[0,0], [0,1], [1,0], [1,1]]:
			for h_ in range(int(h/2)):
				for w_ in range(int(w/2)):
					weights[i+2*h_,j+2*w_,h_,w_] = 0.5
		self.weights = tf.constant(weights)
		output_tensor = tf.einsum('ijkl,jkmn->imnl', self.input_tensor, self.weights)
		print(shape(output_tensor))
		"""
		self.output_tensor = output_tensor
		return output_tensor

	def _simple_lrp(self, R, input_tensor):
		output_tensor = tf.nn.pool(input_tensor, [2, 2], "AVG", "VALID", strides=[2,2])*2
		R = tf.reshape(R, shape(output_tensor))
		R_per_act = tf.divide(R, output_tensor+1e-9)
		R_per_in_act = tf.gradients(output_tensor, input_tensor, grad_ys=R_per_act)[0]
		R_out = tf.multiply(R_per_in_act, input_tensor)
		return R_out

	def simple_lrp(self, R):
		self.R_simple = self._simple_lrp(R, self.input_tensor)
		self.conservation = tf.reduce_sum(R) / tf.reduce_sum(self.R_simple)
		return self.R_simple

	def alphabeta_lrp(self, R, alpha=1.):
		input_plus = tf.nn.relu(self.input_tensor)
		input_minus = tf.nn.relu(-self.input_tensor)

		R_plus_out = self._simple_lrp(R, input_plus)
		R_minus_out = self._simple_lrp(R, input_minus)

		R_out = alpha*R_plus_out + (1.-alpha)*R_minus_out
		return R_out

	def deep_taylor(self, R): return self.alphabeta_lrp(R, 1.)

	def to_numpy(self):
		return modules.Pooling()

	"""
	def simple_lrp(self, R):
		R = tf.reshape(R, shape(self.output_tensor))
		activators_ = tf.einsum('ijkl,jkmn->ijkmnl', self.input_tensor, self.weights)
		R_per_act = tf.divide(R, self.output_tensor+1e-9)  #imnl
		R_out = tf.einsum('ijkmnl,imnl->ijkl', activators_, R_per_act)
		self.R_simple = R_out 
		self.conservation = tf.reduce_sum(R) / tf.reduce_sum(R_out)
		return R_out
	"""

# -------------------------
# Convolution layer
# -------------------------
class Convolution(Layer):
	def __init__(self, w_shape):
		self.w_shape = w_shape
		if len(w_shape) != 4:
			raise Exception("Convolutional Layer: w has to be of rank 4, but is {}. Maybe add None as batch_size dim".format(len(w_shape)))

	def conv2d(self, X, W):
		return tf.nn.conv2d(X, W, [1, 1, 1, 1], padding="VALID")

	def forward(self, input_tensor):
		self.input_tensor = input_tensor
		_, dx1, dx2, channels_x = input_tensor.get_shape().as_list()
		self.weights = weight_variable(self.w_shape)
		self.biases = bias_variable([1, 1, 1, self.w_shape[-1]])
		self.activators = self.conv2d(self.input_tensor, self.weights)
		self.output_tensor = self.activators + self.biases
		return self.output_tensor

	def _simple_lrp(self, R, activators, weights, input_tensor):
		R = tf.reshape(R, shape(activators))
		R_per_act = tf.divide(R, activators+1e-9)
		R_per_in_act = tf.gradients(activators, self.input_tensor, grad_ys=R_per_act)[0]
		R_out = tf.multiply(R_per_in_act, input_tensor)
		return R_out

	def simple_lrp(self, R):
		R_out = self._simple_lrp(R, self.activators, self.weights, self.input_tensor)
		self.R_simple = R_out 
		self.conservation = tf.reduce_sum(R) / tf.reduce_sum(R_out)
		return R_out

	def alphabeta_lrp(self, R, alpha=1.):
		# Split activators into + and -
		input_plus = tf.nn.relu(self.input_tensor)
		input_minus = tf.nn.relu(-self.input_tensor)
		w_plus = tf.nn.relu(self.weights)
		w_minus = tf.nn.relu(-self.weights)

		a_plus1 = self.conv2d(input_plus, w_plus)
		a_plus2 = self.conv2d(input_minus, w_minus)
		a_minus1 = self.conv2d(input_plus, w_minus)
		a_minus2 = self.conv2d(input_minus, w_plus)
		# check if activator decomposition holds:
		self.ab_forward_error = tf.divide(self.activators - (a_plus1+a_plus2 - (a_minus1+a_minus2)), self.activators)

		R_plus1 = tf.multiply(R, tf.divide(a_plus1, a_plus1+a_plus2))
		R_plus2 = tf.multiply(R, tf.divide(a_plus2, a_plus1+a_plus2))
		R_minus1 = tf.multiply(R, tf.divide(a_minus1, a_minus1+a_minus2))
		R_minus2 = tf.multiply(R, tf.divide(a_minus2, a_minus1+a_minus2))

		R_out = (alpha*(self._simple_lrp(R_plus1, a_plus1, w_plus, input_plus)
			+ self._simple_lrp(R_plus2, a_plus2, w_plus, input_plus) )
			+ (1.-alpha)*(self._simple_lrp(R_minus1, a_minus1, w_minus, input_minus)
			+ self._simple_lrp(R_minus2, a_minus2, w_minus, input_minus) ))	

		return R_out


class NextConvolution(Convolution):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.lrp_module = modules.NextConvolution

	def deep_taylor(self, R):
		return self.alphabeta_lrp(R, alpha=1.)
	
class FirstConvolution(Convolution):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.lrp_module = modules.FirstConvolution

	def forward(self, input_tensor):
		input_shape = input_tensor.get_shape().as_list()
		if len(input_shape) < 4:
			h = np.prod(input_shape[1])/28
			print("FirstConvolution: reshape to height:", h)
			input_tensor = tf.reshape(input_tensor, [-1, int(h), 28, 1])
		return super().forward(input_tensor)

	def gradprop(self, DY, W):
		Y = self.conv2d(self.input_tensor, W)
		return tf.gradients(Y, self.input_tensor, DY)[0]

	def deep_taylor(self, R):
		W_plus = tf.nn.relu(self.weights)
		W_minus = -tf.nn.relu(-self.weights)
		X,L,H = self.input_tensor,self.input_tensor*0+utils.lowest,self.input_tensor*0+utils.highest
		Z = self.conv2d(X, self.weights)-self.conv2d(L, W_plus)-self.conv2d(H, W_minus)+1e-09
		S = tf.divide(R, Z)

		R_out = X*self.gradprop(S, self.weights)-L*self.gradprop(S, W_plus)-H*self.gradprop(S, W_minus)
		return R_out

	