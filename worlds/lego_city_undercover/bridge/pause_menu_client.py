"""Client lifecycle for the native pause menu, independent of save delivery."""
import asyncio
import logging
import time

from native_model_transport import configure_pause_menu, NativePlayerBusy


class PauseMenuInstaller:
    def __init__(self,dll,*,configure=configure_pause_menu,clock=time.monotonic):
        self.dll=dll
        self.configure=configure
        self.clock=clock
        self.pid=None
        self.installed=False
        self.retry_at=0
        self.status=None

    def _status(self,value):
        if value==self.status:return None
        self.status=value
        return value

    async def poll(self,session):
        if session.pid!=self.pid:
            self.pid=session.pid
            self.installed=False
            self.retry_at=0
            self.status=None
        if self.installed or self.clock()<self.retry_at:return None
        try:
            result=await asyncio.to_thread(self.configure,session.pid,self.dll)
            if not result.get('installed') or not result.get('enabled'):
                raise RuntimeError('Native pause menu did not acknowledge installation')
        except (OSError,RuntimeError,ValueError) as error:
            # Installation is idempotent and writes no gameplay/save data. A
            # transient failure must neither stop checks nor suppress retries.
            self.retry_at=self.clock()+(1 if isinstance(error,NativePlayerBusy) else 5)
            message='Pausemenü: warte auf Installation – '+str(error)
            changed=self._status(message)
            if changed:logging.warning('Native pause-menu installation deferred: %s',error)
            return changed
        self.installed=True
        logging.info('Native pause menu: Chapter Select installed; 15 chapter entries; chapter activation unavailable')
        return self._status('Pausemenü: Chapter Select aktiv · Kapitelstart noch nicht verfügbar')
