import asyncio

from loguru import logger


class CountDownLatch:
    success_event = asyncio.Event()

    def __init__(self):
        self.__n_coroutines = 0
        self.__done_coroutines = 0
        self.__failed_tasks = 0
        self.__error_tolerance = 0
        self.__completed_sucessfuly = True

    def set_parameters(self, n_to_wait_for: int = 0, n_total: int = 0):
        self.__n_coroutines = n_to_wait_for
        self.__error_tolerance = n_total - n_to_wait_for

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
            self.__n_coroutines = 0
            self.__done_coroutines = 0
            self.__failed_tasks = 0
            self.__error_tolerance = 0
            self.__completed_sucessfuly = True
            self.success_event.clear()

    async def add_failed_task(self):
        logger.debug("Adding one of the tasks to failed queue")
        async with asyncio.Lock():
            self.__failed_tasks += 1

    async def release_if_m_failed(self):
        async with asyncio.Lock():
            if self.__failed_tasks > self.__error_tolerance:
                self.success_event.set()
                logger.debug(
                    f"{self.__failed_tasks} tasks have failed; Aborting the task."
                )
                self.__completed_sucessfuly = False

    def get_failed_tasks(self):
        return self.__failed_tasks

    def has_completed_sucessfuly(self):
        return self.__completed_sucessfuly

    def get_latch_state(self):
        return {
            "n_coroutines": self.__n_coroutines,
            "done_coroutines": self.__done_coroutines,
        }
