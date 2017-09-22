from .lrp.train import *
from .lrp import utils
from . import read_mnist
import os
from matplotlib import pyplot as plt

def linear_test():
	mnist = read_mnist.read_data_sets("{}/datasets/mnist".format(os.environ["TF_PROJECTS"]), one_hot=True)
	
	X = tf.placeholder(tf.float32, shape=[None, 784])
	y_ = tf.placeholder(tf.float32, shape=[None, 10])
	#mlp = Network([Format(), FirstLinear(300), Tanh(), NextLinear(100), Tanh(), NextLinear(10)], X, y_)
	p = Network([Format(), FirstLinear(10)], X, y_)
	R_deeptaylor = p.deep_taylor(y_)
	R_simple = p.mixed_lrp(y_, "simple")
	R_ab = p.mixed_lrp(y_, [["ab", 2.]])
	sess = p.create_session()
	p.load_params("yiha/linear")
	for i in range(1000):
		acc, _ = sess.run([p.accuracy, p.train], feed_dict=p.feed_dict(mnist.train.next_batch(50)))
		print(acc)
	p.save_params("yiha/linear")
	acc = sess.run([p.accuracy], feed_dict=p.feed_dict(mnist.test.next_batch(200)))
	print("Finally: ", acc)

	X, T = mnist.train.next_batch(10); feed_dict=p.feed_dict([X, T])

	for R, name in zip([R_deeptaylor, R_simple, R_ab], ["deeptaylor", "simple", "ab"]):
		h = sess.run(R, feed_dict=feed_dict)
		utils.visualize(h, utils.heatmap, "yiha/linear/"+name+".png")


def activation_test():
	mnist = read_mnist.read_data_sets("{}/datasets/mnist".format(os.environ["TF_PROJECTS"]), one_hot=True)
	
	X = tf.placeholder(tf.float32, shape=[None, 784])
	y_ = tf.placeholder(tf.float32, shape=[None, 10])
	#mlp = Network([Format(), FirstLinear(300), Tanh(), NextLinear(100), Tanh(), NextLinear(10)], X, y_)
	mlp = Network([Format(), FirstConvolution([5, 5, 1, 32]), Abs(), Pooling(),
		NextConvolution([5, 5, 32, 64]), Abs(), Pooling(),
		NextLinear(1024), ReLU(),
		NextLinear(10)], X, y_)
	sess = mlp.create_session()

	"""
	for i in range(1000):
		acc, _ = sess.run([mlp.accuracy, mlp.train], feed_dict=mlp.feed_dict(mnist.train.next_batch(50)))
		print(acc)
	mlp.save_params("yiha/abs")
	"""
	mlp.load_params("yiha/abs")

	acc = sess.run([mlp.accuracy], feed_dict=mlp.feed_dict(mnist.test.next_batch(200)))
	print("Finally: ", acc)

	X, T = mnist.train.next_batch(10); feed_dict=mlp.feed_dict([X, T])

	heatmaps, _ = mlp.get_numpy_deeptaylor(X, T)
	print("h shaoe", heatmaps.shape)
	utils.visualize(heatmaps, utils.heatmap, "yiha/abs/np_deeptaylor.png")

	mlp.close_sess()


def mlp_test():
	mnist = read_mnist.read_data_sets("{}/datasets/mnist".format(os.environ["TF_PROJECTS"]), one_hot=True)
	
	X = tf.placeholder(tf.float32, shape=[None, 784])
	y_ = tf.placeholder(tf.float32, shape=[None, 10])
	
	mlp = Network([Format(), FirstLinear(300), ReLU(), NextLinear(100), ReLU(), NextLinear(10)], X, y_)
	
	R = mlp.deep_taylor(y_)
	R_simple = mlp.mixed_lrp(y_, "simple")
	R_abdt = mlp.mixed_lrp(y_, methods=[["deep_taylor"], ["ab", 1.], ["ab", 1.], ["ab", 1.], ["ab", 1.]])
	R_ab = mlp.mixed_lrp(y_, methods=[["ab", 2.], ["ab", 2.], ["ab", 2.], ["ab", 2.], ["ab", 2.]])
	R_abb = mlp.mixed_lrp(y_, methods=[["abb", 2.], ["abb", 2.], ["abb", 2.], ["abb", 2.], ["abb", 2.]])
	R_simpleb = mlp.mixed_lrp(y_, "simpleb")
	sess = mlp.create_session()

	"""
	for i in range(2000):
		acc, _ = sess.run([mlp.accuracy, mlp.train], feed_dict=mlp.feed_dict(mnist.train.next_batch(50)))
		print(acc)
	mlp.save_params("yiha")
	"""
	mlp.load_params("yiha")
	acc, _ = sess.run([mlp.accuracy, mlp.train], feed_dict=mlp.feed_dict(mnist.test.next_batch(200)))
	print("Finally: ", acc)

	X, T = mnist.train.next_batch(10); feed_dict=mlp.feed_dict([X, T])

	mlp.layerwise_tfnp_test(X, T)

	#mlp.test(X, T)
	print("\n----------------------\n")
	heatmaps, y = sess.run([R, mlp.y], feed_dict=mlp.feed_dict([X, T]))
	utils.visualize(heatmaps, utils.heatmap, "yiha/deeptaylor_tf.png")
	print("Deeptaylor Conservation: ")
	correct_class_relevance = np.sum(y*T, axis=1)
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	heatmaps, _ = mlp.get_numpy_deeptaylor(X, T)
	utils.visualize(X, utils.heatmap, "yiha/x.png")
	utils.visualize(heatmaps, utils.heatmap, "yiha/deeptaylor_np.png")
	print("Numpy Deeptaylor Conservation: ")
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	heatmaps = sess.run(R_abdt, feed_dict=mlp.feed_dict([X, T]))
	utils.visualize(heatmaps, utils.heatmap, "yiha/ab_deeptaylor.png")
	print("AB Deeptaylor Conservation: ")
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	heatmaps = sess.run(R_ab, feed_dict=mlp.feed_dict([X, T]))
	utils.visualize(heatmaps, utils.heatmap, "yiha/ab.png")
	print("AB Conervation: ")
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	heatmaps_simple = sess.run(R_simple, feed_dict=mlp.feed_dict([X, T]))
	utils.visualize(heatmaps_simple, utils.heatmap, "yiha/simple_heatmap.png")
	print("Simple Conservation: ")
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	heatmaps = sess.run(R_simpleb, feed_dict=mlp.feed_dict([X, T]))
	utils.visualize(heatmaps, utils.heatmap, "yiha/simpleb_heatmap.png")
	print("Simple with flat biases Conservation: ")
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	heatmaps = sess.run(R_abb, feed_dict=mlp.feed_dict([X, T]))
	utils.visualize(heatmaps, utils.heatmap, "yiha/abb_heatmap.png")
	print("AB Conservation with flat biases: ")
	mlp.conservation_check(heatmaps, correct_class_relevance)
	input()

	# Again numpy deeptaylor, but now explain a certain class rather than the correct class
	E = np.eye(10)
	for c, e in enumerate(E):
		heatmaps, _ = mlp.get_numpy_deeptaylor(X, e)
		utils.visualize(heatmaps, utils.heatmap, "yiha/class_{}.png".format(c))

	# Show how a zero image looks like, for reference
	nothing, _ = mlp.get_numpy_deeptaylor(X, np.zeros(10))
	utils.visualize(nothing, utils.heatmap, "cooolcnn/nothing.png")

	mlp.close_sess()

def cnn_test():
	mnist = read_mnist.read_data_sets("{}/datasets/mnist".format(os.environ["TF_PROJECTS"]), one_hot=True)
	
	# Create placeholders for the network
	X = tf.placeholder(tf.float32, shape=[None, 784])
	y_ = tf.placeholder(tf.float32, shape=[None, 10])
	discriminant_filter = tf.constant([-1.]*10, dtype=tf.float32) + 2*y_

	# specify a network architecture
	cnn = Network([Format(), FirstConvolution([5, 5, 1, 32]), ReLU(), Pooling(),
		NextConvolution([5, 5, 32, 64]), ReLU(), Pooling(),
		NextLinear(1024), ReLU(),
		NextLinear(10)], X, y_)

	# Get a tensor that calculates deeptaylor explanation for the correct class
	R_simple = cnn.mixed_lrp(y_, "simple")
	#R_deeptaylor = cnn.deep_taylor(y_)

	# instanciate network by creating a session
	sess = cnn.create_session()
	"""
	# train the network for 200 train steps
	for i in range(200):
		acc, _ = sess.run([cnn.accuracy, cnn.train], feed_dict=cnn.feed_dict(mnist.train.next_batch(50)))
		print(acc)
	# save learned params to dir "yuhu"
	cnn.save_params("yuhu")
	"""
	cnn.load_params("yuhu")
	print("Now check out accuracy:")
	acc, = sess.run([cnn.accuracy], feed_dict=cnn.feed_dict(mnist.test.next_batch(200)))
	print("Finally: ", acc)

	# get a batch that we use for testing now
	x, T = mnist.train.next_batch(10)
	feed_dict = cnn.feed_dict([x, T])

	"""
	# Forwarding tests:
	# test if numpy and tensorflow networks are identical
	cnn.layerwise_tfnp_test(x, T)

	# test again if numpy and tensorflow networks are identical:
	# forward the same batch in tf network
	cnn_y = sess.run(cnn.y, feed_dict=cnn.feed_dict([x, T]))
	# get a networ with numpy backend
	npcnn = cnn.to_numpy()
	# use it
	np_y = npcnn.forward(x)
	print("Max error: ",np.absolute(np_y-cnn_y).max())
	"""

	# LRP Testing
	# simple lrp with tensorflow
	cnn.simple_test(feed_dict)

	heatmaps = sess.run(R_simple, feed_dict=feed_dict)
	utils.visualize(heatmaps, utils.heatmap, "cooolcnn/simple_lrp.png")
	print(heatmaps[0])

	"""
	# deeptaylor with tensorflow
	heatmaps = sess.run(R_deeptaylor, feed_dict=feed_dict)
	utils.visualize(heatmaps, utils.heatmap, "cooolcnn/deeptaylor_tf.png")

	# get deeptaylor with numpy implementation
	heatmaps, _ = cnn.get_numpy_deeptaylor(x, T)
	utils.visualize(x, utils.heatmap, "cooolcnn/x.png")
	utils.visualize(heatmaps, utils.heatmap, "cooolcnn/deeptaylor_np.png")
	"""
	cnn.close_sess()