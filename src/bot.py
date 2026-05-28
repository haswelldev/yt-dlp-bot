from abc import ABC, abstractmethod


class Bot(ABC):
    @abstractmethod
    async def run(self) -> None:
        raise NotImplementedError
