"""
Dataset class for BooksCorpus movie review dataset
"""
from typing import Dict, List

from spacy.tokenizer import Tokenizer
from torch.utils.data import Dataset
from spacy.lang.en import English
from tqdm import trange, tqdm
import torch


def freqs_to_maps(path, limit, unk, pad):

    vmap, imap, count = {}, {}, 0
    with open(path, 'r') as infile:

        line = infile.readline()
        while line:
            word, freq = line.split('\t')

            if count == limit-2: 
                break

            line = infile.readline()
            vmap[word] = count
            imap[count] = word
            count += 1

    vmap[unk] = count
    imap[count] = unk
    vmap[pad] = count+1
    imap[count+1] = pad
    return vmap, imap


def sopen(filepath, linecount):

    lines = []
    progress = tqdm(total=linecount, desc='Loading data')
    with open(filepath, 'r') as infile:

        line = infile.readline()
        while line:
            lines.append(line)
            line = infile.readline()
            progress.update(1)

    return lines


class BooksCorpusTokenizer:


    def __init__(self, countpath, start, window, unk, pad, end, vocab):
        self.vmap, self.imap = freqs_to_maps(countpath, vocab, unk, pad)
        self.tokenizer = Tokenizer(English().vocab)
        self.window = window
        self.start = start
        self.vocab = vocab
        self.unk = unk
        self.pad = pad 
        self.end = end


    def tokenize_line(self, line):

        tokens = [
            t.text if t.text in self.vmap else self.unk 
            for t in self.tokenizer(line)
        ]

        if len(tokens) < self.window + 1:
            padding = [self.pad for i in range(self.window+1-len(tokens))]
            tokens = padding + tokens

        ids = torch.Tensor([self.vmap[t] for t in tokens])
        ids = ids.type(torch.LongTensor)
        ids = torch.nn.functional.one_hot(ids, self.vocab)
        xids, yid = ids[:-1], ids[-1]

        return xids, yid


    def tokenize(self, lines):

        X = torch.empty((len(lines), self.window, self.vocab))
        Y = torch.empty((len(lines), self.vocab))

        for i in range(len(lines)):
            x, y = self.tokenize_line(lines[i])
            X[i], Y[i] = x, y

        return X, Y

    
    def decode_line(self, x):
        ids = torch.argmax(x, dim=1)
        tokens = [self.imap[i.item()] for i in ids]
        return tokens


    def decode(self, x):
        lines = []

        for i in range(x.shape[0]):
            lines.append(self.decode_line(x[i]))

        return lines


class BooksCorpus(Dataset):


    def __init__(self, datapath, linecount):
        super(Dataset, self).__init__()

        if linecount is None:
            self.data = open(datapath, 'r').readlines()

        else:
            self.data = sopen(datapath, linecount)


    def __len__(self) -> int:

        return len(self.data)


    def __getitem__(self, idx):

        return self.data[idx].strip()


