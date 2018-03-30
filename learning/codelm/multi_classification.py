#classifying if it's an opcode or not

#framework

#extract_and_prepare
#generate_datasets
#generate_batch
#generate_model
#train_model
#test_model
import tensorflow as tf
import numpy as np
import utilities as ut
import random  
import word2vec as w2v

class Data(object):
    
    def __init__(self):
        self.percentage = 80
        self.embedder = w2v.Word2Vec()
        self.num_classes = 5

    def get_embedding(self, token_data, sym_dict, mem_start):
        
        dict_data, _, dictionary, reverse_dictionary = self.embedder.build_dataset(token_data)
        final_embeddings = self.embedder.train_skipgram(dict_data, len(dictionary), reverse_dictionary, sym_dict, mem_start)
        return dict_data, dictionary, final_embeddings

    def extract_and_prepare_data(self,cnx,format):

        raw_data = ut.get_data(cnx,format,[])
        token_data = list()
        for row in raw_data:
            token_data.extend(row[0])
        print len(token_data)

        offsets_filename = '/data/scratch/charithm/projects/cmodel/database/offsets.txt'
        sym_dict, mem_start = ut.get_sym_dict(offsets_filename)
        offsets = ut.read_offsets(offsets_filename)

        dict_data, dictionary, final_embeddings = self.get_embedding(token_data, sym_dict, mem_start)
            
        embedding_size = self.embedder.embedding_size
    
        #create the entire dataset from the learnt embeddings
        self.x = np.ndarray(shape = [len(dict_data),embedding_size]) 
        self.y = np.ndarray(shape = [len(dict_data),1])

        for i,token in enumerate(token_data):        
            self.x[i] = final_embeddings[dict_data[i]]
            if token >= offsets[0] and token < offsets[4]:
                self.y[i] = 0
            elif token >= offsets[1] and token < offsets[2]:
                self.y[i] = 1
            elif token == offsets[2]:
                self.y[i] = 2
            elif token == offsets[3]:
                self.y[i] = 3
            elif token >= offsets[4]:
                self.y[i] = 4
            else:
                assert False

    def generate_datasets(self):
        assert self.x.shape[0] == self.y.shape[0]
        size = self.y.shape[0]
        split = (size * self.percentage) // 100
        self.train_x  = self.x[:split,:]
        self.train_y = self.y[:split]
        self.test_x = self.x[(split + 1):,:]
        self.test_y = self.y[(split + 1):]
        
    def generate_batch(self, batch_size):
        population = range(self.train_x.shape[0])
        embedding_size = self.embedder.embedding_size
        selected = random.sample(population,batch_size)
        batch_x = np.ndarray(shape = [batch_size, embedding_size])
        batch_y = np.ndarray(shape = [batch_size,1])
        for i,index in enumerate(selected):
            batch_x[i] = self.train_x[index,:]
            batch_y[i] = self.train_y[index]

        return batch_x, batch_y
  
    
class Model(object):

    def __init__(self, data):
        self.data = data
        self.learning_rate = 1.0
        self.epochs = 10
        self.batch_size = 1000

    def generate_model(self):

        embedding_size = self.data.embedder.embedding_size
        num_classes = self.data.num_classes
        learning_rate = self.learning_rate
        
        self.graph = tf.Graph()
        with self.graph.as_default():

            self.x = tf.placeholder(tf.float32, shape = [None, embedding_size])
            self.y_raw = tf.placeholder(tf.float32, shape = [None,1])
            self.y_onehot = tf.one_hot(tf.cast(self.y_raw, tf.int32), num_classes)
            self.y = tf.reshape(self.y_onehot, [-1,num_classes])
        
            self.W = tf.Variable(tf.random_normal(shape = [embedding_size, num_classes], dtype = tf.float32))
            self.b = tf.Variable(tf.random_normal(shape = [1,num_classes], dtype = tf.float32))
        
            self.output = tf.add(tf.matmul(self.x,self.W),self.b)
            
            self.centropy = tf.losses.softmax_cross_entropy(self.y,self.output)
    
            self.optimizer = tf.train.GradientDescentOptimizer(learning_rate = learning_rate).minimize(self.centropy)
        
            self.init_op = tf.global_variables_initializer()
        
            #accuracy operator
            self.final_output = tf.nn.softmax(self.output)
            self.final_output = tf.Print(self.final_output,[tf.shape(self.final_output)])

            self.final_output = tf.argmax(self.final_output, axis = 1)
            self.final_output = tf.Print(self.final_output,[tf.shape(self.final_output)])

            self.final_output = tf.reshape(self.final_output, [-1,1])
            self.final_output = tf.Print(self.final_output,[tf.shape(self.final_output)])

            correct = tf.equal(self.final_output,tf.cast(self.y_raw, tf.int64))

            self.accuracy = tf.reduce_mean(tf.cast(correct,tf.float32))

    def train_model(self):

        epochs = self.epochs

        with tf.Session(graph=self.graph) as sess:
            # initialise the variables
            writer = tf.summary.FileWriter('/tmp/tensorflow/', graph=tf.get_default_graph())

            sess.run(self.init_op)
            total_batch = int(self.data.train_x.shape[0]) / self.batch_size
            for epoch in range(self.epochs):
                avg_cost = 0
                for i in range(total_batch):
                    batch_x, batch_y = self.data.generate_batch(self.batch_size)
                    _, c = sess.run([self.optimizer, self.centropy], 
                                    feed_dict={self.x: batch_x, self.y_raw: batch_y})
                    avg_cost += c / total_batch
                print("Epoch:", (epoch + 1), "cost =", "{:.3f}".format(avg_cost))
            W = self.W.eval()
            b = self.b.eval()
        return W,b

    def test_model(self,params):
        W,b = params
        with tf.Session(graph=self.graph) as sess:
            print(sess.run([self.accuracy, self.final_output], feed_dict={self.x: self.data.test_x, self.y_raw: self.data.test_y, self.W: W, self.b: b}))
 
        print self.data.test_y



