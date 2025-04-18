from datetime import datetime, timedelta
import logging
import math
from typing import List
import numpy as np
import png
import pytz
from PIL import Image
import os
from patterns import digit_patterns, arrow_patterns, signal_patterns
from util import Color, EntrieEnum, GlucoseItem, TreatmentEnum

class PixelMatrix:
    def __init__(self, matrix_size: int, min_glucose: int, max_glucose: int, GLUCOSE_LOW, GLUCOSE_HIGH, night_brightness):
        self.min_glucose = min_glucose
        self.matrix_size = matrix_size
        self.max_glucose = max_glucose
        self.GLUCOSE_LOW = GLUCOSE_LOW
        self.GLUCOSE_HIGH = GLUCOSE_HIGH
        self.night_brightness = night_brightness
        self.pixels = [[[0, 0, 0] for _ in range(matrix_size)] for _ in range(matrix_size)]

    def set_formmated_entries(self, formmated_entries):
        self.formmated_entries = formmated_entries

    def set_formmated_treatments(self, formmated_treatments):
        self.formmated_treatments = formmated_treatments

    def set_arrow(self, arrow: str):
        self.arrow = arrow

    def set_glucose_difference(self, glucose_difference: int):
        self.glucose_difference = glucose_difference

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int):
        if 0 <= x < self.matrix_size and 0 <= y < self.matrix_size:
            self.pixels[y][x] = [r, g, b]

    def get_pixel(self, x: int, y: int) -> List[int]:
        return self.pixels[y][x]

    def paint_background(self, color):
        for y in range(self.matrix_size):
            for x in range(self.matrix_size):
                self.pixels[y][x] = color
                
    def set_interpoleted_pixel(self, x: int, y: int, glucose_start:int, color: List[int], percentil: float):
        start_y = self.glucose_to_y_coordinate(glucose_start) + 2
        y = start_y + y
        if 0 <= x < self.matrix_size and 0 <= y < self.matrix_size:
            interpolated_color = self.interpolate_color(Color.black, color, percentil, 0, 1)
            self.pixels[y][x] = interpolated_color

    def draw_vertical_line(self, x: int, color: List[int], glucose: int, height: int, enable_five=False, blink=False):
        start_y = self.glucose_to_y_coordinate(glucose) + 2
        if start_y + height < self.matrix_size:
            y_max = start_y + height
        else:
            y_max = self.matrix_size
        
        for y in range(start_y, y_max):
            temp_color = color
            if blink:
                if y % 2 == 0:
                    temp_color = self.fade_color(color, 0.2)
            if enable_five:
                if not self.is_five_apart(start_y, y):
                    temp_color = self.fade_color(color, 0.5)

            self.set_pixel(x, y, *temp_color)

    def draw_horizontal_line(self, glucose: int, color: List[int], start_x: int, finish_x: int):
        y = self.glucose_to_y_coordinate(glucose) + 1
        finish_x = min(start_x + finish_x, self.matrix_size)
        start_x = max(start_x, 0)
        for x in range(start_x, finish_x):
            self.set_pixel(x, y, *color)

    def get_out_of_range_glucose_str(self, glucose: int) -> str:
        if glucose <= 39:
            return "LOW"
        elif glucose >= 400:
            return "HIGH"
        else:
            return glucose
    
    def is_glucose_out_of_range(self, glucose: int) -> bool:
        return glucose <= 39 or glucose >= 400

    def get_digits_width(self, glucose_str: str) -> int:
        width = 0
        for digit in glucose_str:
            width += len(digit_patterns()[digit][0])
        return width

    def display_glucose_on_matrix(self, glucose_value: int):
        digit_width, digit_height, spacing = 3, 5, 1

        if self.is_glucose_out_of_range(glucose_value):
            glucose_str = self.get_out_of_range_glucose_str(glucose_value)
            color = Color.red
        else:
            glucose_str = str(glucose_value)
            color = Color.white


        digits_width = len(glucose_str) * spacing + self.get_digits_width(glucose_str)

        arrow_pattern = arrow_patterns().get(self.arrow, np.zeros((5, 5)))
        arrow_width = arrow_pattern.shape[1] + spacing
        signal_width = 3 + spacing

        glucose_diff_str = str(abs(self.glucose_difference))
        glucose_diff_width = len(glucose_diff_str) * (digit_width + spacing)
        total_width = digits_width + arrow_width + signal_width + glucose_diff_width
        start_x = (self.matrix_size - total_width) // 2
        y_position = (self.matrix_size - digit_height) // 2 - 13

        x_position = start_x
        for digit in glucose_str:
            digit_pattern = digit_patterns()[digit]
            for i, row in enumerate(digit_pattern):
                for j, value in enumerate(row):
                    if value:
                        self.set_pixel(x_position + j, y_position + i, *color)
            x_position += self.get_digit_width(digit) + spacing

        for i, row in enumerate(arrow_pattern):
            for j, value in enumerate(row):
                if value:
                    self.set_pixel(x_position + j, y_position + i, *color)
        x_position += arrow_width

        signal_pattern = signal_patterns()[self.get_glucose_difference_signal()]
        for i, row in enumerate(signal_pattern):
            for j, value in enumerate(row):
                if value:
                    self.set_pixel(x_position + j, y_position + i, *color)
        x_position += signal_width

        for digit in glucose_diff_str:
            digit_pattern = digit_patterns()[digit]
            for i, row in enumerate(digit_pattern):
                for j, value in enumerate(row):
                    if value:
                        self.set_pixel(x_position + j, y_position + i, *color)
            x_position += digit_width + spacing

    def get_digit_width(self, digit: str) -> int:
        return len(digit_patterns()[digit][0])

    def display_entries(self, formmated_entries: List[GlucoseItem]):
        self.glucose_plot = [[] for _ in range(self.matrix_size)]
        
        now = datetime.now()

        for entry in formmated_entries:
            time_diff_minutes = (now - entry.date).total_seconds() / 60
            idx = int(time_diff_minutes // 5)
            
            if 0 <= idx < self.matrix_size:
                self.glucose_plot[idx].append(entry.glucose)

        for idx, glucose_values in enumerate(self.glucose_plot):
            if glucose_values:
                median_glucose = int(np.average(glucose_values))
                x = self.matrix_size - idx - 1
                y = self.glucose_to_y_coordinate(median_glucose)
                r, g, b = self.determine_color(median_glucose)
                self.set_pixel(x, y, r, g, b)

    def get_low_brightness_pixels(self):
        brightness = self.get_brightness_on_hour()
        low_brightness_pixels = [[[0, 0, 0] for _ in range(self.matrix_size)] for _ in range(self.matrix_size)]

        for x in range(0, self.matrix_size):
            for y in range(0, self.matrix_size):
                low_brightness_pixels[y][x] = self.fade_color(self.get_pixel(x, y), brightness)

        return low_brightness_pixels

    def generate_image(self, output_file="output_image.png"):
        logging.info("Generating image.")
        brightness = self.get_brightness_on_hour()

        if brightness != 1.0:
            low_brightness_pixels = self.get_low_brightness_pixels()
            png_matrix = []
            for row in low_brightness_pixels:
                png_matrix.append([val for pixel in row for val in pixel])
        else:
            png_matrix = []
            for row in self.pixels:
                png_matrix.append([val for pixel in row for val in pixel])

        with open(output_file, "wb") as f:
            writer = png.Writer(self.matrix_size, self.matrix_size, greyscale=False)
            writer.write(f, png_matrix)
        logging.info(f"Image generated and saved as {output_file}.")
        
    def generate_timer_gif(self, output_file=os.path.join("temp", "output_gif.gif")):
        frame_files = []
        frame_files.append(os.path.join("temp", "frame-0.png"))
        for index in range(1,6):
            self.set_pixel(0, index - 1, *self.fade_color(Color.white, 0.1))

        self.generate_image("temp/frame-0.png")

        for index in range(1,6):
            self.set_pixel(0, index - 1, *Color.white)
            frame_filename = os.path.join("temp", f"frame-{index}.png")
            self.generate_image(frame_filename)
            frame_files.append(frame_filename)

        frames = [Image.open(frame) for frame in frame_files]
        frames[0].save(
            output_file,
            save_all=True,
            append_images=frames[1:],
            duration=60000,  # 1 minute in milliseconds
            loop=0
        )

    def glucose_to_y_coordinate(self, glucose: int) -> int:
        glucose = max(self.min_glucose, min(glucose, self.max_glucose))
        available_y_range = self.matrix_size - 6
        normalized = (glucose - self.min_glucose) / (self.max_glucose - self.min_glucose)
        return int((1 - normalized) * available_y_range) + 5

    def get_brightness_on_hour(self, timezone_str="America/Recife") -> float:
        local_tz = pytz.timezone(timezone_str)
        current_time = datetime.now(local_tz)
        current_hour = current_time.hour

        if 21 <= current_hour or current_hour < 6:
            return self.night_brightness
        else:
            return 1.0
        
    def determine_color(self, glucose: int, entry_type=EntrieEnum.SGV) -> List[int]:
        if entry_type == EntrieEnum.MBG:
            return Color.white

        if glucose < self.GLUCOSE_LOW - 10:
            return self.interpolate_color(Color.red, Color.yellow, glucose, self.get_min_sgv(), self.GLUCOSE_LOW - 10,)
        if glucose > self.GLUCOSE_HIGH + 10:
            return self.interpolate_color(Color.yellow, Color.red, glucose, self.GLUCOSE_HIGH + 10, self.get_max_sgv())
        elif glucose <= self.GLUCOSE_LOW or glucose >= self.GLUCOSE_HIGH:
            return Color.yellow
        else:
            return Color.green

    def interpolate_color(self, low_color: List[int], high_color: List[int], value: int, min_value: int, max_value: int) -> List[int]:
        if value < min_value:
            value = min_value
        elif value > max_value:
            value = max_value

        t = (value - min_value) / (max_value - min_value)

        r = int(low_color[0] + t * (high_color[0] - low_color[0]))
        g = int(low_color[1] + t * (high_color[1] - low_color[1]))
        b = int(low_color[2] + t * (high_color[2] - low_color[2]))

        return [r, g, b]

    def get_glucose_difference_signal(self) -> str:
        return '-' if self.glucose_difference < 0 else '+'

    def get_max_sgv(self) -> int:
        max_sgv = 0
        for entry in self.formmated_entries:
            max_sgv = max(max_sgv, entry.glucose)

        return max_sgv

    def get_min_sgv(self) -> int:
        min_sgv = self.formmated_entries[0].glucose
        for entry in self.formmated_entries:
            min_sgv = min(min_sgv, entry.glucose)

        return min_sgv

    def is_five_apart(self, init: int, current: int) -> bool:
        return (current - init + 1) % 5 == 0

    def fade_color(self, color: List[int], percentil: float) -> List[int]:
        fadded_color = []
        for item in color:
            fadded_color.append(math.ceil(item * percentil))
        return fadded_color