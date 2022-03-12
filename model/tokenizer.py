from collections import defaultdict
from typing import Tuple, Dict, List
import pickle

from tqdm import trange, tqdm
import torch

from abc import ABC, abstractmethod


class Tokenizer(ABC):

    @abstractmethod
    def tokenize(self):
        pass


class BytePairTokenizer(Tokenizer):


    def __init__(self) -> None:
        """ Initialize byte pair tokenizer
        """

        self.corpus = defaultdict(int)
        self.vocab = defaultdict(int) 
        self.vocab_to_index = {}
        self.index_to_vocab = {}
        self.eow = ' </w>'
        self.eol = '</eol> '
        self.unk = '<unk>'
        self.pad = '<pad>'


    def add_to_corpus(self, data: List[str]) -> None:
        """ Add list of words to corpus

        Args:
            data: list of words to add
        """
        tokens = [' '.join(list(t)) + self.eow for t in data]
        for token in tokens:
            self.corpus[token] += 1


    def add_to_vocab(self, data):
        """ Add characters from list of words to vocabulary

        Args:
            data: list of words to add
        """
        chars = set([char_ for token in data for char_ in list(token)])
        for char_ in chars:
            self.vocab[tuple(char_)] += 1


    def trim_corpus(self, count: int) -> None:
        """ Trim members of corpus with a frequency less than provided count

        Args:
            count: frequency threshold for removing corpus words
        """

        keys = list(self.corpus.keys())
        for key in tqdm(keys):
            if self.corpus[key] < count:
                del(self.corpus[key])


    def build_indices(self) -> None:
        """ Build indices mapping vocabulary to indices and indices to
            vocabulary
        """

        keys = list(self.vocab.keys())
        for i in range(len(keys)):
            pair = ''.join(keys[i])
            self.vocab_to_index[pair] = i
            self.index_to_vocab[i] = pair

        for token in [self.eow, self.eol, self.unk, self.pad]:
            idx = len(self.vocab_to_index)
            pair = ''.join(token)
            self.vocab_to_index[pair] = idx
            self.index_to_vocab[idx] = pair


    def merge_max_pair(self) -> bool:
        """ Get maximum frequency byte pair from corpus and merge these byte
            pairs for every member of the corpus 

        Returns:
            (bool): whether or not merging is successful
        """

        maxpair = self.get_max_pair()
        success = False

        if maxpair is not None:
            search = ' '.join(maxpair)
            replace = ''.join(maxpair)
            self.vocab[maxpair] += 1
            success = True

            words = list(self.corpus.keys())
            for word in words:
                if search in word:
                    replacement = word.replace(search, replace)
                    self.corpus[replacement] = self.corpus[word]
                    del(self.corpus[word])

        return success


    def get_max_pair(self) -> Tuple[str, str]:
        """ Get maximum frequency byte pair from corpus

        Returns:
            (Tuple[str, str]): maximum frequency byte pair
        """

        pairs = defaultdict(int)
        for word in self.corpus.keys():
            tokens = word.split(' ')

            for i in range(1, len(tokens)):
                pair = tuple(tokens[i-1:i+1])
                pairs[pair] += 1

        maxpair = None
        if len(pairs) > 0:
            maxpair = max(pairs, key=pairs.get)

        return maxpair


    def segment(self, token: str) -> str:
        """ Segment provided token into whitespace-separated bytes

        Args:
            token: string to tokenize

        Returns:
            (str): whitespace-separated string of bytes
        """

        token = ' '.join(list(token)) + self.eow

        while True:
            chars = token.split(' ')
            pairs = self.get_char_pair_freqs(chars)

            if len(pairs) == 0:
                break

            else:
                idx1, idx2 = max(pairs, key=pairs.get)
                token = self.merge_chars(chars, idx1, idx2)

        return token


    def tokenize(self, batch: List[str], window_size: int, 
                     segmented: bool=False) -> torch.Tensor:
        """ Transform batch of lines into tensor of one-hot tokens

        Args:
            batch: list of lines
            window_size: number of tokens to consider (will slice/pad to this
                         length)
            segmented: flag indicating whether files have already been segmented
                       or not

        Returns:
            (torch.Tensor): tensor of one-hot vectors for each token in each
                            line
        """

        batch_ids = []
        vocab_size = len(self.vocab_to_index)

        for line in batch:

            tokens = line.split(' ')
            if not tokenized:
                tokens = [self.segment(token) for token in tokens]

            ids = self.tokens_to_ids(tokens)
            ids = self.pad_ids(ids, window_size)
            batch_ids.append(ids)

        batch_ids = torch.Tensor(batch_ids).type(torch.LongTensor)
        batch_ids = torch.nn.functional.one_hot(batch_ids, vocab_size)
        batch_ids = batch_ids.type(torch.FloatTensor)

        return batch_ids


    def tokens_to_ids(self, tokens: List[str]) -> List[int]:
        """ Turn list of tokens into list of ids

        Args:
            tokens: list of tokens to transform

        Return:
            (List[int]): list of corresponding token ids
        """

        ids = [] 
        for token in tokens:
            if token in self.vocab_to_index:
                ids.append(self.vocab_to_index[token])

            else:
                ids.append(self.vocab_to_index[self.unk])

        return ids


    def pad_ids(self, ids: List[int], size: int) -> List[int]:
        """ Pad list of ids to specified length, cuts list if too long

        Args:
            ids: list of ids to pad
            size: length to pad/slice to

        Return:
            (List[int]): padded list of ids
        """

        ids = ids[:size]
        difference = size - len(ids) 

        if len(ids) < size:
            ids += [self.vocab_to_index[self.pad] for i in range(difference)]

        return ids


    def get_char_pair_freqs(self, chars: List[str]) -> \
                            Dict[Tuple[int, int], int]:
        """ Get indices of all byte pairs in sequence of bytes and return
            dictionary mapping indicies of byte pairs and their frequency in the
            vocabulary

        Args:
            chars: sequence of bytes to extract pair frequencies from

        Returns:
            (Dict[Tuple[int, int], int]): dict mapping tuple of byte indices in
                                          sequence to the byte pair frequency
        """

        pairs = {}
        for i in range(1, len(chars)):
            pair = tuple([chars[i-1], chars[i]])
            if pair in self.vocab:
                pairs[(i-1, i)] = self.vocab[pair]

        return pairs


    def merge_chars(self, chars: List[str], idx1: int, idx2: int) -> str:
        """ Joins charactars at provided indices of byte list and returns
            concatenated string of new bytes

        Args:
            chars: sequence of bytes to merge pair in
            idx1: index of first byte to merge
            idx2: index of second byte to merge

        Returns:
            (str): concatenated string with relevant byte pair merged 
        """

        chars = chars[:idx1] + [''.join(chars[idx1:idx2+1])] + chars[idx2+1:]
        return ' '.join(chars)


    def save(self, path: str) -> None:
        """ Save tokenizer at provided path

        Args:
            path: filepath where tokenizer should be saved
        """

        checkpoint = {
            'corpus': self.corpus,
            'vocab': self.vocab,
            'word_token': self.eow,
            'vocab_to_index': self.vocab_to_index,
            'index_to_vocab': self.index_to_vocab 
        }

        with open(path, 'wb') as outfile:
            pickle.dump(checkpoint, outfile)

    
    def load(self, path):
        """ Load tokenizer from provided path

        Args:
            path: filepath where tokenizer should be loaded from 
        """

        with open(path, 'rb') as infile:
            checkpoint = pickle.load(infile)
            self.corpus = checkpoint['corpus'] 
            self.vocab = checkpoint['vocab'] 
            self.eow = checkpoint['word_token'] 
            self.vocab_to_index = checkpoint['vocab_to_index'] 
            self.index_to_vocab  = checkpoint['index_to_vocab'] 


