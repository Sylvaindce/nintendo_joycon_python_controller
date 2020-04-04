import signal
import struct
import time

import hid

# import pynput


class ServiceExit(Exception):
    """
    Custom exception which is used to trigger the clean exit
    of all running threads and the main program.
    """

    pass


class nintendo_joycon(object):

    # Rumble data (320Hz 0.0f 160Hz 0.0f) is neutral
    __rumble_data = b"\x00\x01\x40\x40\x00\x01\x40\x40"

    __buttons_status = {
        "b_pos": [3, 4, 5],
        "val": {
            b"\x01": ["Y", "-", "DOWN"],
            b"\x02": ["X", "+", "UP"],
            b"\x04": ["B", "R-STICK", "RIGHT"],
            b"\x08": ["A", "L-STICK", "LEFT"],
            b"\x10": ["SR", "HOME", "SR"],
            b"\x20": ["SL", "CAPTURE", "SL"],
            b"\x40": ["R", "--", "L"],
            b"\x80": ["ZR", "CHARGING GRIP", "ZL"],
        },
    }

    def __init__(self, config):
        signal.signal(signal.SIGTERM, nintendo_joycon.service_shutdown)
        signal.signal(signal.SIGINT, nintendo_joycon.service_shutdown)
        self.__vendor_id = config.get("vendor_id", 1406)
        self.__product_id = config.get("product_id", 8199)
        self.__global_packet_nbr = 0

        self.__device = None
        self.__open_device()
        self.__setup_joycon()
        self.__read_device()

    def __open_device(self):
        try:
            self.__device = hid.Device(vid=self.__vendor_id, pid=self.__product_id)
        except IOError as err:
            raise IOError(f"Joy-Con failed to connect: {err}")

    def __close_device(self):
        try:
            self.__device.close()
        except Exception as err:
            raise Exception(err)

    def __send_data(self, rumble_type=b"\x01", sub_cmd_id=None, sub_cmd_data=None):
        """
            Frame prototype
            buf[0] =  Rumble_type; // 0x10 for rumble only or 0x01 for rumble data and subcmd)
            buf[1] = GlobalPacketNumber; // Increment by 1 for each packet sent. It loops in 0x0 - 0xF range.
            buf[2:9] = Rumble Data; // Neutral rumble data is [0x00 0x01 0x40 0x40 0x00 0x01 0x40 0x40]
            buf[10] = Sub Command ID;
            buf[11:] = Sub Command Data and Sub Command Data Len;
        """
        try:
            self.__device.write(
                rumble_type
                + self.global_packet_nbr
                + self.__rumble_data
                + sub_cmd_id
                + sub_cmd_data
            )
            self.global_packet_nbr = self.__global_packet_nbr + 1
        except Exception as err:
            print(err)

    def __setup_joycon(self):
        # Buffer size 49 because 13-48 is 6-Axis data.
        self.__buffer_size = 49
        # Enable 6-Axis data
        self.__send_data(sub_cmd_id=b"\40", sub_cmd_data=b"\x01")
        time.sleep(0.06)
        # Set input report mode to Standard full mode. Pushes current state @60Hz
        self.__send_data(sub_cmd_id=b"\x03", sub_cmd_data=b"\x30")

    def __read_device(self):
        try:
            while True:
                msg = self.__device.read(self.__buffer_size)
                for bit_pos in self.__buttons_status["b_pos"]:
                    tmp_bval = msg[bit_pos].to_bytes(1, byteorder="big")
                    if tmp_bval in self.__buttons_status["val"]:
                        print(
                            self.__buttons_status["val"][tmp_bval][
                                bit_pos - len(self.__buttons_status["b_pos"])
                            ]
                        )
        except ServiceExit:
            self.__close_device()
        except struct.error:
            self.__read_device()

    @property
    def global_packet_nbr(self):
        return self.__global_packet_nbr.to_bytes(1, byteorder="big")

    @global_packet_nbr.setter
    def global_packet_nbr(self, nbr):
        """
            Range from 0 to 15 following the documentation
        """
        self.__global_packet_nbr = nbr & 0xF

    @staticmethod
    def service_shutdown(signum, frame):
        print("Caught signal %d" % signum)
        raise ServiceExit


if __name__ == "__main__":
    devices = hid.enumerate(0, 0)

    for device in devices:
        if "Joy-Con" in device.get("product_string", ""):
            # print(device)
            nintendo_joycon(device)
