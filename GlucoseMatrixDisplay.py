import subprocess
import numpy as np
import requests
import time
import json
import datetime

class GlucoseMatrixDisplay:
    def __init__(self, config_path='config.json', matrix_size=32, min_glucose=60, max_glucose=180):
        self.matrix_size = matrix_size
        self.min_glucose = min_glucose
        self.max_glucose = max_glucose
        self.max_time = 20 #minutes
        self.config = self.load_config(config_path)
        self.ip = self.config.get('ip')
        self.url = self.config.get('url')
        self.GLUCOSE_LOW = self.config.get('low bondary glucose')
        self.GLUCOSE_HIGH = self.config.get('high bondary glucose')
        self.os = self.config.get('os', 'linux').lower()
        self.arrow = ''
        self.glucose_difference = 0
        self.first_value = None
        self.second_value = None
        self.update_glucose_command()

    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise Exception(f"Error loading configuration file: {e}")

    def update_glucose_command(self):
        self.json_data = self.fetch_json_data()
        if self.json_data:
            self.points = self.parse()
            if self.os == 'windows':
                self.command = f"run_in_venv.bat --address {self.ip} --pixel-color {self.list_to_command_string()}"
            else:
                self.command = f"./run_in_venv.sh --address {self.ip} --pixel-color {self.list_to_command_string()}"


    def run_command(self):
        print(self.command)
        try:
            result = subprocess.run(self.command, shell=True, check=True)
            if result.returncode != 0:
                print("Command failed.")
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")

    def run_command_in_loop(self):
        self.run_command()
        while True:
            time.sleep(10)
            current_json = self.fetch_json_data()
            if current_json != self.json_data:
                self.update_glucose_command()
                self.run_command()

    def fetch_json_data(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching data: {e}")

    def glucose_to_y_coordinate(self, glucose):
        glucose = max(self.min_glucose, min(glucose, self.max_glucose))
        available_y_range = self.matrix_size - 6
        normalized = (glucose - self.min_glucose) / (self.max_glucose - self.min_glucose)
        return int((1 - normalized) * available_y_range) + 5

    def set_arrow(self, formmated_json):
        for item in formmated_json:
            if item.type == "sgv":
                self.arrow = item.direction
                break

    def parse(self):
        pixels = []
        formmated_json = []
        first_value_saved_flag = False

        for item in self.json_data:
            if item.get("type") == "sgv":
                formmated_json.append(GlucoseItem("sgv",
                                                  item.get("sgv"),
                                                  item.get("dateString"),
                                                  item.get("direction")))
            elif item.get("type") == "mbg":
                formmated_json.append(GlucoseItem("mbg",
                                                  item.get("mbg"),
                                                  item.get("dateString")))

        for item in formmated_json:
            if item.type == "sgv" and not first_value_saved_flag:
                self.first_value = item.glucose
                first_value_saved_flag = True
                continue
            if item.type == "sgv":
                self.second_value = item.glucose
                break

        self.set_glucose_difference()
        self.set_arrow(formmated_json)
        self.main_color = None
        pixels = self.display_glucose_on_matrix(self.first_value)

        for idx, entry in enumerate(formmated_json):
            self.main_color = self.determine_color(entry.glucose, entry_type=entry.type)

            x = self.matrix_size - idx - 1
            y = self.glucose_to_y_coordinate(entry.glucose)
            r, g, b = self.main_color
            pixels.append([x, y, r, g, b])

        y_low = self.glucose_to_y_coordinate(self.GLUCOSE_LOW)
        y_high = self.glucose_to_y_coordinate(self.GLUCOSE_HIGH)

        pixels.extend(self.draw_horizontal_line(y_low, self.fade_color(Color.white,0.8), pixels, 4))
        pixels.extend(self.draw_horizontal_line(y_high, self.fade_color(Color.white,0.8), pixels, 4))

        for indx, item in enumerate(formmated_json):
            print(f"{indx:02d}: {item.type} - {item.glucose}")
        return pixels

    def determine_color(self, glucose, entry_type="sgv"):
        if entry_type == "mbg":
            return Color.blue

        if glucose <= self.GLUCOSE_LOW - 10 or glucose >= self.GLUCOSE_HIGH + 10:
            return Color.red
        elif glucose <= self.GLUCOSE_LOW or glucose >= self.GLUCOSE_HIGH:
            return Color.yellow
        else:
            return Color.green

    def list_to_command_string(self, delimiter='-'):
        return ' '.join([delimiter.join(map(str, sublist)) for sublist in self.points])

    def set_glucose_difference(self):
        self.glucose_difference = int(self.first_value) - int(self.second_value)

    def get_glucose_difference_signal(self):
        return '-' if self.glucose_difference < 0 else '+'

    def digit_patterns(self):
        return {
            '0': np.array([[1, 1, 1], [1, 0, 1], [1, 0, 1], [1, 0, 1], [1, 1, 1]]),
            '1': np.array([[0, 1, 0], [1, 1, 0], [0, 1, 0], [0, 1, 0], [1, 1, 1]]),
            '2': np.array([[1, 1, 1], [0, 0, 1], [1, 1, 1], [1, 0, 0], [1, 1, 1]]),
            '3': np.array([[1, 1, 1], [0, 0, 1], [1, 1, 1], [0, 0, 1], [1, 1, 1]]),
            '4': np.array([[1, 0, 1], [1, 0, 1], [1, 1, 1], [0, 0, 1], [0, 0, 1]]),
            '5': np.array([[1, 1, 1], [1, 0, 0], [1, 1, 1], [0, 0, 1], [1, 1, 1]]),
            '6': np.array([[1, 1, 1], [1, 0, 0], [1, 1, 1], [1, 0, 1], [1, 1, 1]]),
            '7': np.array([[1, 1, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1]]),
            '8': np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1], [1, 0, 1], [1, 1, 1]]),
            '9': np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1], [0, 0, 1], [1, 1, 1]])
        }

    def arrow_patterns(self):
        return {
            'SingleUp': np.array([[0, 0, 1, 0, 0],
                                  [0, 1, 1, 1, 0],
                                  [1, 0, 1, 0, 1],
                                  [0, 0, 1, 0, 0],
                                  [0, 0, 1, 0, 0]]),

            'DoubleUp': np.array([[0, 1, 0, 0, 1, 0],
                                  [1, 1, 1, 1, 1, 1],
                                  [0, 1, 0, 0, 1, 0],
                                  [0, 1, 0, 0, 1, 0],
                                  [0, 1, 0, 0, 1, 0]]),

            'FortyFiveUp': np.array([[0, 1, 1, 1, 1],
                                     [0, 0, 0, 1, 1],
                                     [0, 0, 1, 0, 1],
                                     [0, 1, 0, 0, 1],
                                     [1, 0, 0, 0, 0]]),

            'Flat': np.array([[0, 0, 1, 0, 0],
                              [0, 0, 0, 1, 0],
                              [1, 1, 1, 1, 1],
                              [0, 0, 0, 1, 0],
                              [0, 0, 1, 0, 0]]),

            'FortyFiveDown': np.array([[1, 0, 0, 0, 0],
                                       [0, 1, 0, 0, 0],
                                       [0, 0, 1, 0, 1],
                                       [0, 0, 0, 1, 1],
                                       [0, 0, 1, 1, 1]]),

            'DoubleDown': np.array([[0, 1, 0, 0, 1, 0],
                                    [0, 1, 0, 0, 1, 0],
                                    [0, 1, 0, 0, 1, 0],
                                    [1, 1, 1, 1, 1, 1],
                                    [0, 1, 0, 0, 1, 0]]),

            'SingleDown': np.array([[0, 0, 1, 0, 0],
                                    [0, 0, 1, 0, 0],
                                    [1, 0, 1, 0, 1],
                                    [0, 1, 1, 1, 0],
                                    [0, 0, 1, 0, 0]])
        }

    def signal_patterns(self):
        return {
            '-': np.array([[0, 0, 0],
                           [0, 0, 0],
                           [1, 1, 1],
                           [0, 0, 0],
                           [0, 0, 0]]),

            '+': np.array([[0, 0, 0],
                           [0, 1, 0],
                           [1, 1, 1],
                           [0, 1, 0],
                           [0, 0, 0]])
        }

    def draw_horizontal_line(self, y, color, old_pixels, boarder_len):
        pixels = []
        for x in list(range(boarder_len)) + list(range(self.matrix_size - boarder_len, self.matrix_size)):
            already_paintted = False
            for x_old,y_old,_,_,_ in old_pixels:
                if x_old == x and y_old == y:
                    already_paintted = True
                    break
            if not already_paintted: pixels.append([x, y, *color])
        return pixels

    def draw_pattern(self, color, matrix, pattern, position, scale=1):
        start_x, start_y = position
        for i, row in enumerate(pattern):
            for j, value in enumerate(row):
                if value:
                    x, y = start_x + j * scale, start_y + i * scale
                    if 0 <= x < self.matrix_size and 0 <= y < self.matrix_size:
                        matrix[x, y] = color

    def matrix_to_pixel_list(self, matrix):
        pixel_list = []
        for x in range(self.matrix_size):
            for y in range(self.matrix_size):
                if not np.all(matrix[x, y] == 0):
                    pixel_list.append((x, y, *matrix[x, y]))
        return pixel_list

    def paint_background(self):
        return f" --fullscreen-color {round(self.color[0]*0.1)}-{round(self.color[1]*0.1)}-{round(self.color[2]*0.1)}"

    def display_glucose_on_matrix(self, glucose_value):
        matrix = np.zeros((self.matrix_size, self.matrix_size, 3), dtype=int)
        glucose_str = str(glucose_value)
        color = Color.white
        digit_width, digit_height, spacing = 3, 5, 1
        digits_width = len(glucose_str) * (digit_width + spacing)
        arrow_width, signal_width = 5 + spacing, 3 + spacing
        glucose_diff_str = str(abs(self.glucose_difference))
        glucose_diff_width = len(glucose_diff_str) * (digit_width + spacing)
        total_width = digits_width + arrow_width + signal_width + glucose_diff_width
        start_x = (self.matrix_size - total_width) // 2
        y_position = (self.matrix_size - digit_height) // 2 - 13

        position_x = start_x
        for digit in glucose_str:
            self.draw_pattern(color, matrix, self.digit_patterns()[digit], (position_x, y_position))
            position_x += digit_width + spacing

        self.draw_pattern(color, matrix, self.arrow_patterns().get(self.arrow, np.zeros((5, 5))), (position_x, y_position))
        position_x += arrow_width
        self.draw_pattern(color, matrix, self.signal_patterns()[self.get_glucose_difference_signal()], (position_x, y_position))
        position_x += signal_width

        for digit in glucose_diff_str:
            self.draw_pattern(color, matrix, self.digit_patterns()[digit], (position_x, y_position))
            position_x += digit_width + spacing

        return self.matrix_to_pixel_list(matrix)

    def is_recent_data(self):
        current_time_millis = int(datetime.datetime.now().timestamp() * 1000)
        first_mills = next((item.get("mills") for item in self.json_data if item.get("mills") is not None), None)

        if first_mills is None:
            raise ValueError("No 'mills' timestamp found in the JSON data.")

        time_difference = (current_time_millis - (first_mills - 3600 * 1000 * 3)) / (1000 * 60)
        return time_difference > self.max_time
    
    def fade_color(self, color, percentil):
        fadded_color = []
        for item in color:
            fadded_color.append(int(item * percentil))
        return fadded_color

class Color:
    red = [255, 20, 10]
    green = [54, 187, 10]
    yellow = [244, 190, 0]
    purple = [250, 0, 105]
    white = [230, 170, 60]
    blue = [10, 150, 155]

class GlucoseItem:
    def __init__(self, type, glucose, dateString, direction = None):
        self.type = type
        self.glucose = glucose
        self.dateString = dateString
        self.direction = direction

if __name__ == "__main__":
    GlucoseMatrixDisplay().run_command_in_loop()
