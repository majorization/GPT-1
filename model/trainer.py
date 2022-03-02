from typing import Dict, List

from tqdm import tqdm
import torch


class Trainer:


    def __init__(self, model: torch.nn.Module, tokenizer: 'Tokenizer',
                 optimizer: torch.optim, loss_fn: torch.nn, 
                 scheduler: torch.optim.lr_scheduler) -> None:
        """ Initialize trainer module

        Args:
            model: model to be trained
            tokenizer: tokenizer for tokenizing list of strings
            optimizer: optimizer for learning
            loss_fn: loss function to optimize
            scheduler: learning rate scheduler
        """
        self.tokenizer = tokenizer
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.loss_fn = loss_fn
        self.model = model


    def reset_metrics(self) -> None:
        """ Zero out internal metrics
        """

        self.total_loss = 0
        self.batch_loss = 0
        self.total_err = 0
        self.batch_err = 0
        self.count = 0


    def train(self, loader: torch.utils.data.DataLoader) -> (float, float):
        """ Train on batches in loader

        Args:
            loader: data loader containing training data in batches
        Returns:
            (float): average loss 
            (float): average error
        """

        progress = tqdm(total=len(loader), desc='Train Loss: | Err: ')
        self.reset_metrics()

        for batch in loader:
            self.optimizer.zero_grad()
            loss = self.step(batch)
            loss.backward()
            self.optimizer.step()

            desc = (f'Train Loss: {self.batch_loss:.10f}' 
                    f'| Err: {self.batch_err:.10f}')
            progress.set_description(desc)
            progress.update(1)

        self.scheduler.step()
        return self.batch_loss, self.batch_err


    def validate(self, loader: torch.utils.data.DataLoader) -> (float, float):
        """ Validate using batches in loader

        Args:
            loader: data loader containing validation data in batches

        Returns:
            (float): average loss 
            (float): average error
        """

        progress = tqdm(total=len(loader), desc='Val Loss: | Err: ')
        self.reset_metrics()

        with torch.no_grad():
            for batch in loader:
                loss = self.step(batch)

                desc = (f'Val Loss: {self.batch_loss:.10f}' 
                        f'| Err: {self.batch_err:.10f}')
                progress.set_description(desc)
                progress.update(1)

        return self.batch_loss, self.batch_err


    def step(self, batch: List[str]):
        """ Run training / validation step on provided batch

        Args:
            batch: list of strings to run model on
        """

        tokens = self.tokenizer.tokenize(batch).to(self.model.device)
        output = self.model(tokens)
        yhat = torch.argmax(output, dim=2)[:, 1:]
        y = torch.argmax(tokens, dim=2)[:, 1:]

        batch_size, sequence_length, dimension = tokens.shape
        labels = y.reshape((batch_size * (sequence_length - 1)))
        output = output[:, 1:, :].reshape((
            batch_size * (sequence_length-1),
            dimension
        ))

        loss = self.loss_fn(output, labels)
        self.total_err += torch.sum((yhat != y).float()).item()
        self.total_loss += loss.item()
        self.count += len(batch)

        self.batch_err = self.total_err / (self.count * y.shape[1])
        self.batch_loss = self.total_loss / self.count

        return loss


    def get_checkpoint(self) -> Dict[str, str]:
        """  Get dictionary of state dictionaries for checkpointing 

        Returns:
            (Dict[str, str]): dictionary mapping trainer components to their
                              state dictionaries for checkpointing
        """

        return {
            'optimizer': self.optimizer.state_dict(),
            'scheduler': self.scheduler.state_dict(),
            'model': self.model.state_dict(),
            'tokenizer': self.tokenizer
        }
