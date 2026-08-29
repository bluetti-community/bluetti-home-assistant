import logging

import aiohttp

from .bluetti import Bluetti
from .unify_response import UnifyResponse
from ..const import Method
from ..const import AppPath
from ..model.product import UserProduct
from ..model.product_decrypt_info import UserProductDecryptInfo

import os


class ProductClient(Bluetti):
    """Class describing for the BLUETTI products."""

    __LOGGER__ = None
    """The api client logger."""

    def __init__(self, httpSession: aiohttp.ClientSession, accessToken,hass):
        super().__init__(httpSession, accessToken,hass)

    @property
    def logger(self) -> logging.Logger:
        """
        Get the api client logger.
        定义API客户端的日志记录器
        """
        if self.__LOGGER__ is None:
            self.__LOGGER__ = logging.getLogger(__name__ + "." + __class__.__name__)
        return self.__LOGGER__
    

    async def async_download_and_save_file(self,down_url: str = None,save_dir: str = None,filename: str = None)->str:
        if down_url == None or down_url == '':
            self.logger.error(f'filename:{filename} down_url:{down_url} is null')
            return
        if os.path.exists(save_dir) == False:
            await self._hass.async_add_executor_job(os.makedirs, save_dir)
        file_path = os.path.join(save_dir, filename)
        if os.path.exists(file_path) == True:
            return file_path

        try:
            async with self._httpSession.get(down_url, timeout=aiohttp.ClientTimeout(total=30),headers={ "Authorization": f"{self._accessToken}"}) as response:
                response.raise_for_status()

                def _write_chunks(chunks):
                    with open(file_path, "wb") as f:
                        for chunk in chunks:
                            f.write(chunk)

                chunks = []
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    chunks.append(chunk)

                await self._hass.async_add_executor_job(_write_chunks, chunks)
                return file_path
        except Exception as e:
            self.logger.error(f"back down load failed：{e}", exc_info=True)
        return None

    async def get_user_products(self) -> UnifyResponse[list[UserProduct]]:
        """
        Get user belongs power stations/devices by send an api request.
        请求接口，获取用户所属的发电站/设备信息。
        """
        return await self._request(
            list[UserProduct],
            Method.GET,
            AppPath.SMART_HOME_API+"/ha/v2/devices",
        )

    async def get_device_status(self, sns: str = None) -> UnifyResponse[list[UserProduct]]:
        """
        轮询获取设备状态
        """
        return await self._request(
            list[UserProduct],
            Method.GET,
            AppPath.SMART_HOME_API+"/ha/v1/deviceStates",
            params={'sns': sns}
        )

    async def control_device(self, payload: str = None):
        """
        控制设备
        """
        return await self._request(
            dict,
            method=Method.POST,
            path=AppPath.SMART_HOME_API+"/ha/v1/fulfillment",
            body=payload
        )
    async def bind_devices(self, payload: str = None):
        """
        bind devices
        """
        return await self._request(
            dict,
            method=Method.POST,
            path=AppPath.SMART_HOME_API+"/ha/v1/bindDevices",
            body=payload
        )
    
    async def get_decrypt_info(self, deviceSn: str = None) -> UnifyResponse[UserProductDecryptInfo]:
        """
        get ble encrypt key
        """
        return await self._request(
            UserProductDecryptInfo,
            method=Method.GET,
            path=AppPath.DECODE_CENTER_API+"/gprotobuf/v1/getDeviceDecodeInfo",
            params={'deviceSn': deviceSn,'isGetEncryptKey':'true'}
        )