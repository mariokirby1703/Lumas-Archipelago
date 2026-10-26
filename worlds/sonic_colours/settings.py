import settings

class OptionalFilePath(settings.OptionalUserFilePath):
    def exists(self):
        return bool(self) and super().exists()

    def resolve(self):
        return super().resolve() if self else ''


class SonicColoursSettings(settings.Group):
    class ISOFile(settings.UserFilePath):
        description='Original Sonic Colours Wii PAL SNCP8P Rev0 ISO'
        copy_to=None
    class ToolPath(OptionalFilePath):
        description='Optional Wiimms ISO Tools executable'
    class DolphinPath(OptionalFilePath):
        description='Dolphin emulator executable (selected once and remembered)'
    iso_file:ISOFile=ISOFile('Sonic Colours.iso')
    wit_path:ToolPath=ToolPath('')
    dolphin_path:DolphinPath=DolphinPath('')
    auto_start:bool=True
