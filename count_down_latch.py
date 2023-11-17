from loguru import logger
import asyncio


class CountDownLatch:
    success_event = asyncio.Event()

    def __init__(self):
        self.__n_coroutines = 0
        self.__done_coroutines = 0

    def set_n_coroutines(self, n):
        self.__n_coroutines = n

    async def release_if_n_acquired(self):
        async with asyncio.Lock():
            if self.__done_coroutines >= self.__n_coroutines:
                logger.debug(f"The first {self.__done_coroutines} coroutines are done")
                self.success_event.set()

    async def coroutine_done(self):
        async with asyncio.Lock():
            self.__done_coroutines += 1
            logger.debug(f"One of the coroutines is done")

    async def wait(self):
        logger.debug(f"Waiting for coroutines to finish")
        await self.success_event.wait()

    async def reset(self):
        logger.debug("Reseting latch to default state")
        async with asyncio.Lock():
            self.__done_coroutines = 0
            self.__n_coroutines = 0
            self.success_event.clear()

    def get_latch_state(self):
        return {
            "n_coroutines": self.__n_coroutines,
            "done_coroutines": self.__done_coroutines
        }