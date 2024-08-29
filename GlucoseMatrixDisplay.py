import numpy as np
import requests
import os
import time
import json

class GlucoseMatrixDisplay:
    def __init__(self, config_path='config.json', matrix_size=32, min_glucose=60, max_glucose=180):
        self.matrix_size = matrix_size
        self.min_glucose = min_glucose
        self.max_glucose = max_glucose
        self.config = self.load_config(config_path)
        self.ip = self.config.get('ip')
        self.url = self.config.get('url')
        self.arrow = ''
        self.glucose_difference = 0
        self.update_glucose_data()

    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise Exception(f"Error loading configuration file: {e}")

    def update_glucose_data(self):
        self.json_data = self.fetch_json_data()
        if not self.json_data:
            return
        self.points = self.parse_glucose_data()
        self.command = f"run_in_venv.sh --address {self.ip} --pixel-color {self.list_to_command_string()}"

    def run_command(self):
        print(self.command)
        exit_code = os.system(self.command)
        if exit_code != 0:
            print(f"Command failed with exit code {exit_code}")
            
    def run_command_in_loop(self):
        self.run_command()
        while True:
            time.sleep(30)
            current_json = self.fetch_json_data()
            if current_json != self.json_data:
                self.update_glucose_data()
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


    def parse_glucose_data(self):
        colors = []
        self.first_value = self.json_data[0].get("sgv")
        self.second_value = self.json_data[1].get("sgv")
        self.set_glucose_difference()
        
        for idx, entry in enumerate(self.json_data):
            glucose = entry.get("sgv")
            if glucose is not None:
                if idx == 0:
                    self.arrow = entry.get("direction", "Flat")
                    colors = self.display_glucose_on_matrix(glucose)
                x = self.matrix_size - idx - 1
                y = self.glucose_to_y_coordinate(glucose)
                r, g, b = self.determine_color(glucose)
                colors.append([x, y, r, g, b])
        return colors

    def determine_color(self, glucose):
        GLUCOSE_LOW = 70
        GLUCOSE_HIGH = 180
        BOUNDARY_THRESHOLD = 10

        if glucose <= GLUCOSE_LOW - BOUNDARY_THRESHOLD or glucose >= GLUCOSE_HIGH + BOUNDARY_THRESHOLD:
            return (255, 20, 10)  # Red
        elif glucose <= GLUCOSE_LOW or glucose >= GLUCOSE_HIGH:
            return (244, 190, 0)  # Yellow
        else:
            return (54, 187, 10)  # Green

    def list_to_command_string(self, delimiter='-'):
        return ' '.join([delimiter.join(map(str, sublist)) for sublist in self.points])

    def set_glucose_difference(self):
        self.glucose_difference = int(self.first_value) - int(self.second_value)
        
    def get_glucose_difference_signal(self):
        if  self.glucose_difference < 0:
            return '-'
        else:
            return '+'


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
            'SingleUp': np.array([[0, 1, 0],
                                  [1, 1, 1],
                                  [0, 1, 0],
                                  [0, 1, 0],
                                  [0, 1, 0]]),
            
            'DoubleUp': np.array([[0, 1, 0, 0, 0, 1, 0],
                                  [1, 1, 1, 0, 1, 1, 1],
                                  [0, 1, 0, 0, 0, 1, 0],
                                  [0, 1, 0, 0, 0, 1, 0],
                                  [0, 1, 0, 0, 0, 1, 0]]),
            
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
            
            'DoubleDown': np.array([[0, 1, 0, 0, 0, 1, 0],
                                    [0, 1, 0, 0, 0, 1, 0],
                                    [0, 1, 0, 0, 0, 1, 0],
                                    [1, 1, 1, 0, 1, 1, 1],
                                    [0, 1, 0, 0, 0, 1, 0]]),
            
            'SingleDown': np.array([[0, 1, 0],
                                    [0, 1, 0],
                                    [0, 1, 0],
                                    [1, 1, 1],
                                    [0, 1, 0]])
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

    def draw_digit(self, color, matrix, digit, position, scale=1):
        pattern = self.digit_patterns()[digit]
        start_x, start_y = position

        for i in range(pattern.shape[0]):
            for j in range(pattern.shape[1]):
                if pattern[i, j]:
                    x = start_x + j * scale
                    y = start_y + i * scale
                    if 0 <= x < self.matrix_size and 0 <= y < self.matrix_size:
                        matrix[x, y] = color

    def draw_arrow(self, color, matrix, arrow, position, scale=1):
        pattern = self.arrow_patterns()[arrow]
        start_x, start_y = position

        for i in range(pattern.shape[0]):
            for j in range(pattern.shape[1]):
                if pattern[i, j]:
                    x = start_x + j * scale
                    y = start_y + i * scale
                    if 0 <= x < self.matrix_size and 0 <= y < self.matrix_size:
                        matrix[x, y] = color

    def draw_signal(self, color, matrix, signal, position, scale=1):
        pattern = self.signal_patterns()[signal]
        start_x, start_y = position
        for i in range(pattern.shape[0]):
            for j in range(pattern.shape[1]):
                if pattern[i, j]:
                    x = start_x + j * scale
                    y = start_y + i * scale
                    if 0 <= x < self.matrix_size and 0 <= y < self.matrix_size:
                        matrix[x, y] = color

    def matrix_to_pixel_list(self, matrix):
        pixel_list = []
        for x in range(self.matrix_size):
            for y in range(self.matrix_size):
                if not np.all(matrix[x, y] == 0):
                    pixel_list.append((x, y, *matrix[x, y]))
        return pixel_list

    def display_glucose_on_matrix(self, glucose_value):
        matrix = np.zeros((self.matrix_size, self.matrix_size, 3), dtype=int)
        glucose_str = str(glucose_value)
        color = (230, 170, 60)  # Color for the digits, arrow, and signal
        digit_width = 3
        digit_height = 5
        spacing = 1

        # Calculate width for the digits
        digits_width = len(glucose_str) * (digit_width + spacing)

        # Calculate width for the arrow (assuming a fixed width of 5 for arrows)
        arrow_width = 5 + spacing

        # Calculate width for the signal
        signal_width = 3 + spacing

        # Calculate width for the glucose difference digits
        glucose_diff_str = str(abs(self.glucose_difference))
        glucose_diff_width = len(glucose_diff_str) * (digit_width + spacing)

        # Total width required for all components
        total_width = digits_width + arrow_width + signal_width + glucose_diff_width

        # Calculate the starting x position to center the display on the X-axis
        start_x = (self.matrix_size - total_width) // 2
        y_position = (self.matrix_size - digit_height) // 2 - 13  # Keep Y-position as before

        # Draw each digit of the glucose value
        for idx, digit in enumerate(glucose_str):
            x_position = start_x + idx * (digit_width + spacing)
            self.draw_digit(color, matrix, digit, (x_position, y_position))

        # Draw the arrow
        arrow_x_position = start_x + digits_width
        self.draw_arrow(color, matrix, self.arrow, (arrow_x_position, y_position))

        # Draw the signal
        signal_x_position = arrow_x_position + arrow_width
        self.draw_signal(color, matrix, self.get_glucose_difference_signal(), (signal_x_position, y_position))

        # Draw each digit of the glucose difference
        for idx, digit in enumerate(glucose_diff_str):
            x_position = signal_x_position + signal_width + idx * (digit_width + spacing)
            self.draw_digit(color, matrix, digit, (x_position, y_position))
        
        return self.matrix_to_pixel_list(matrix)

if __name__ == "__main__":
    GlucoseMatrixDisplay().run_command_in_loop()

# Example usage:
# display = GlucoseMatrixDisplay()
# display.run_command()
