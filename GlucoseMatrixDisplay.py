import subprocess
import numpy as np
import requests
import time
import json
import datetime
import pytz
import png
import logging
from http.client import RemoteDisconnected
from patterns import digit_patterns, arrow_patterns, signal_patterns

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GlucoseMatrixDisplay:
    def __init__(self, config_path='config.json', matrix_size=32, min_glucose=60, max_glucose=180):
        self.matrix_size = matrix_size
        self.min_glucose = min_glucose
        self.max_glucose = max_glucose
        self.max_time = 1200000 #milliseconds
        self.config = self.load_config(config_path)
        self.ip = self.config.get('ip')
        self.url_entries = f"{self.config.get('url')}/entries.json?count=40"
        self.url_treatments = f"{self.config.get('url')}/treatments.json?count=40"
        self.url_ping_entries = f"{self.config.get('url')}/entries.json?count=1"
        self.GLUCOSE_LOW = self.config.get('low bondary glucose')
        self.GLUCOSE_HIGH = self.config.get('high bondary glucose')
        self.os = self.config.get('os', 'linux').lower()
        self.night_brightness = float(self.config.get('night_brightness', 0.3))
        self.arrow = ''
        self.glucose_difference = 0
        self.first_value = None
        self.second_value = 0
        self.formmated_entries_json = []
        self.formmated_treatments_json = []
        self.today_bolus = 0
        self.newer_id = None
        self.unblock_bluetooth()
        self.update_glucose_command()

    def load_config(self, config_path):
        try:
            logging.info(f"Loading configuration from {config_path}")
            with open(config_path, 'r') as file:
                config = json.load(file)
                logging.info(f"Configuration loaded successfully: {config}")
                return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error loading configuration file: {e}")
            raise Exception(f"Error loading configuration file: {e}")

    def update_glucose_command(self, image_path="./output_image.png"):
        logging.info("Updating glucose command.")
        self.json_entries_data = self.fetch_json_data(self.url_entries)
        self.json_treatments_data = self.fetch_json_data(self.url_treatments)

        if self.json_entries_data:
            self.points = self.parse()
            self.generate_image()
            if self.os == 'windows':
                self.command = f"run_in_venv.bat --address {self.ip} --image true --set-image {image_path}"
            else:
                self.command = f"./run_in_venv.sh --address {self.ip} --image true --set-image {image_path}"
        logging.info(f"Command updated: {self.command}")

    def generate_image(self, width=32, height=32):
        logging.info("Generating image.")
        brightness = self.get_brightness_on_hour()
        matrix = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]

        if brightness != 1.0:
            for x, y, r, g, b in self.points:
                matrix[y][x] = self.fade_color((r, g, b), brightness)
        else:
            for x, y, r, g, b in self.points:
                matrix[y][x] = (r, g, b)

        png_matrix = []
        for row in matrix:
            png_matrix.append([val for pixel in row for val in pixel])

        with open("output_image.png", "wb") as f:
            writer = png.Writer(width, height, greyscale=False)
            writer.write(f, png_matrix)
        logging.info("Image generated and saved as output_image.png.")

    def run_command(self):
        logging.info(f"Running command: {self.command}")
        try:
            result = subprocess.run(self.command, shell=True, check=True)
            if result.returncode != 0:
                logging.error("Command failed.")
            else:
                logging.info(f"Command executed successfully, with last glucose: {self.first_value}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed with error: {e}")

    def run_command_in_loop(self):
        logging.info("Starting command loop.")
        while True:
            try:
                ping_json = self.fetch_json_data(self.url_ping_entries)[0]
                print(f"ping_json.get('_id'): {ping_json.get('_id')} self.newer_id: {self.newer_id}")
                if not ping_json or self.is_old_data(ping_json) and "./images/nocgmdata.png" not in self.command:
                    logging.info("Old or missing data detected, updating to no data image.")
                    self.update_glucose_command("./images/nocgmdata.png")
                    self.run_command()
                elif ping_json.get("_id") != self.newer_id:
                    logging.info("New glucose data detected, updating display.")
                    self.json_entries_data = self.fetch_json_data(self.url_entries)
                    self.newer_id = ping_json.get("_id")
                    self.update_glucose_command()
                    self.run_command()
                time.sleep(5)
            except Exception as e:
                logging.error(f"Error in the loop: {e}")
                time.sleep(60)

    def reset_formmated_jsons(self):
        self.formmated_entries_json = []
        self.formmated_treatments_json = []
        self.today_bolus = 0

    def fetch_json_data(self, url, retries=5, delay=60, fallback_delay=300):
        attempt = 0
        while True:
            try:
                logging.info(f"Fetching glucose data from {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                logging.info("Glucose data fetched successfully.")
                return response.json()

            except RemoteDisconnected as e:
                logging.error(f"Remote end closed connection on attempt {attempt + 1}: {e}")
                self.update_glucose_command("./images/no_wifi.png")
                self.run_command()

            except requests.exceptions.ConnectionError as e:
                logging.error(f"Connection error on attempt {attempt + 1}: {e}")

            except requests.exceptions.Timeout as e:
                logging.error(f"Request timed out on attempt {attempt + 1}: {e}")

            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching data on attempt {attempt + 1}: {e}")

            # Handle retries and delays
            attempt += 1
            if attempt < retries:
                logging.info(f"Retrying in {delay} seconds... (Attempt {attempt} of {retries})")
                time.sleep(delay)
            else:
                logging.error(f"Max retries ({retries}) reached. Retrying in {fallback_delay} seconds.")
                attempt = 0  # Reset attempts after max retries
                time.sleep(fallback_delay)  # Wait longer before retrying again

    def glucose_to_y_coordinate(self, glucose):
        glucose = max(self.min_glucose, min(glucose, self.max_glucose))
        available_y_range = self.matrix_size - 6
        normalized = (glucose - self.min_glucose) / (self.max_glucose - self.min_glucose)
        return int((1 - normalized) * available_y_range) + 5

    def set_arrow(self):
        for item in self.formmated_entries_json:
            if item.type == "sgv":
                self.arrow = item.direction
                break

    def parse(self):
        pixels = []

        self.generate_list_from_entries_json()
        self.generate_list_from_treatments_json()
        self.extract_first_and_second_value()
        self.set_glucose_difference()
        self.set_arrow()
        self.y_low = self.glucose_to_y_coordinate(self.GLUCOSE_LOW)
        self.y_high = self.glucose_to_y_coordinate(self.GLUCOSE_HIGH)
        treatments = self.get_treatment_x_values()

        pixels = self.display_glucose_on_matrix(self.first_value)

        for idx, entry in enumerate(self.formmated_entries_json[:self.matrix_size]):
            x = self.matrix_size - idx - 1
            y = self.glucose_to_y_coordinate(entry.glucose)
            r, g, b = self.determine_color(entry.glucose, entry_type=entry.type)
            pixels.append([x, y, r, g, b])


        pixels.extend(self.draw_horizontal_line(self.y_low, self.fade_color(Color.white,0.1), pixels, self.matrix_size))
        pixels.extend(self.draw_horizontal_line(self.y_high, self.fade_color(Color.white,0.1), pixels, self.matrix_size))

        for treatment in treatments:
            pixels.extend(self.draw_vertical_line(treatment[0],
                                                  self.fade_color(Color.blue, 0.3) if treatment[2] == "Bolus" else self.fade_color(Color.orange, 0.3),
                                                  pixels,
                                                  self.y_high,
                                                  treatment[1]))

        self.today_bolus = self.get_todays_bolus()
        
        self.reset_formmated_jsons()
        return pixels

    def extract_first_and_second_value(self):
        first_value_saved_flag = False
        for item in self.formmated_entries_json:
            if item.type == "sgv" and not first_value_saved_flag:
                self.first_value = item.glucose
                first_value_saved_flag = True
                continue
            if item.type == "sgv":
                self.second_value = item.glucose
                break

    def check_wifi(self):
        """Checks Wi-Fi access by pinging Google's DNS server"""
        logging.info("Checking Wi-Fi connection.")
        try:
            subprocess.check_output(["ping", "-c", "1", "8.8.8.8"], timeout=5)
            logging.info("Wi-Fi is available.")
            return True
        except subprocess.CalledProcessError:
            logging.error("Wi-Fi not available.")
            return False

    def generate_list_from_entries_json(self):
        for item in self.json_entries_data:
            treatment_date = datetime.datetime.strptime(item.get("dateString"), "%Y-%m-%dT%H:%M:%S.%fZ")
            if item.get("type") == "sgv":
                self.formmated_entries_json.append(GlucoseItem("sgv",
                                                  item.get("sgv"),
                                                  treatment_date,
                                                  item.get("direction")))
            elif item.get("type") == "mbg":
                self.formmated_entries_json.append(GlucoseItem("mbg",
                                                  item.get("mbg"),
                                                  treatment_date))
            
            if len(self.formmated_entries_json) == self.matrix_size:
                break

    def generate_list_from_treatments_json(self):
        for item in self.json_treatments_data:
            time = datetime.datetime.strptime(item.get("created_at"), "%Y-%m-%dT%H:%M:%S.%fZ")
            if item.get("eventType") == "Carbs":
                self.formmated_treatments_json.append(TreatmentItem("Carbs",
                                                  time,
                                                  item.get("carbs")))
            elif item.get("eventType") == "Bolus":
                self.formmated_treatments_json.append(TreatmentItem("Bolus",
                                                  time,
                                                  item.get("insulin")))
            elif item.get("eventType") == "Exercise":
                self.formmated_treatments_json.append(ExerciseItem("Exercise",
                                                  time,
                                                  item.get("duration")))

    def paint_around_value(self, x, y, color, painted_pixels):
        surrounding_pixels = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                new_x = x + dx
                new_y = y + dy
                already_paintted = False
                for x_old,y_old,_,_,_ in painted_pixels:
                    if x_old == new_x and y_old == new_y:
                        already_paintted = True
                        break
                if 0 <= new_x < self.matrix_size and 5 <= new_y < self.matrix_size and not already_paintted:
                    surrounding_pixels.append([new_x, new_y, *self.fade_color(color, .2)])
        return surrounding_pixels

    def determine_color(self, glucose, entry_type="sgv"):
        if entry_type == "mbg":
            return Color.white

        if glucose < self.GLUCOSE_LOW - 10 or glucose > self.GLUCOSE_HIGH + 10:
            return Color.red
        elif glucose <= self.GLUCOSE_LOW or glucose >= self.GLUCOSE_HIGH:
            return Color.yellow
        else:
            return Color.green

    def set_glucose_difference(self):
        self.glucose_difference = int(self.first_value) - int(self.second_value)

    def get_glucose_difference_signal(self):
        return '-' if self.glucose_difference < 0 else '+'

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

    def draw_vertical_line(self, x, color, old_pixels, low_y, height):
        pixels = []
        for y in list(range(low_y, low_y + height + 1)):
            already_paintted = False
            for x_old,y_old,_,_,_ in old_pixels:
                if x_old == x and y_old == y:
                    already_paintted = True
                    break
            if not already_paintted: pixels.append([ x, y, *color])
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
            self.draw_pattern(color, matrix, digit_patterns()[digit], (x_position, y_position))
            x_position += digit_width + spacing

        self.draw_pattern(color, matrix, arrow_pattern, (x_position, y_position))
        x_position += arrow_width
        self.draw_pattern(color, matrix, signal_patterns()[self.get_glucose_difference_signal()], (x_position, y_position))
        x_position += signal_width

        for digit in glucose_diff_str:
            self.draw_pattern(color, matrix, digit_patterns()[digit], (x_position, y_position))
            x_position += digit_width + spacing

        return self.matrix_to_pixel_list(matrix)

    def is_old_data(self, json):
        created_at_str = json.get('sysTime')
        
        if created_at_str is None:
            raise ValueError("No 'sysTime' timestamp found in the JSON data.")
        
        created_at = datetime.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

        current_time = datetime.datetime.now(datetime.timezone.utc)

        time_difference_ms = (current_time - created_at).total_seconds() * 1000

        time_difference_sec = time_difference_ms / 1000
        minutes = int(time_difference_sec // 60)
        seconds = int(time_difference_sec % 60)

        logging.info(f"The data is {minutes:02d}:{seconds:02d} old.")
        
        return time_difference_ms > self.max_time

    def fade_color(self, color, percentil):
        fadded_color = []
        for item in color:
            fadded_color.append(int(item * percentil))
        return fadded_color

    def unblock_bluetooth(self):
        try:
            logging.info("Attempting to unblock Bluetooth...")
            subprocess.run(['sudo', 'rfkill', 'unblock', 'bluetooth'], check=True, text=True, capture_output=True)
            logging.info(f"Bluetooth unblocked successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to unblock Bluetooth: {e.stderr}")

    def calculate_time_difference(self):
        current_time = datetime.datetime.now()
        time_difference = current_time - self.formmated_entries_json[0].dateString
        minutes_difference = time_difference.total_seconds() // 60
        return int(minutes_difference)

    def get_brightness_on_hour(self, timezone_str="America/Recife"):
        local_tz = pytz.timezone(timezone_str)
        current_time = datetime.datetime.now(local_tz)
        current_hour = current_time.hour

        if 21 <= current_hour or current_hour < 6:
            return self.night_brightness
        else:
            return 1.0

    def get_todays_bolus(self):
        now = datetime.datetime.now()
        total_bolus = 0
        for item in self.formmated_treatments_json:
            if item.type != "Bolus":
                continue
            if now.date() == item.date.date():
                total_bolus += item.amount
            else:
                break

        return total_bolus

    def get_treatment_x_values(self):
        treatment_x_values = []

        if not self.formmated_entries_json:
            logging.warning("No glucose entries available.")
            return treatment_x_values

        first_entry_time = self.formmated_entries_json[0].dateString
        last_entry_time = self.formmated_entries_json[-1].dateString

        # Check if treatments fall within the range
        for treatment in self.formmated_treatments_json:
            if treatment.type not in ("Bolus","Carbs"):
                continue
            if treatment.date > first_entry_time or treatment.date < last_entry_time:
                continue

            # Find the closest glucose entry to this treatment
            closest_entry = min(self.formmated_entries_json, key=lambda entry: abs(treatment.date - entry.dateString))
            x_value = self.formmated_entries_json.index(closest_entry)
            treatment_x_values.append((self.matrix_size - x_value - 1,
                                       max(treatment.amount, self.y_high - self.y_low),
                                       treatment.type))  # x-value and treatment amount for height

        return treatment_x_values
class Color:
    red = [255, 20, 10]
    green = [70, 167, 10]
    yellow = [244, 170, 0]
    purple = [250, 0, 105]
    white = [230, 170, 80]
    blue = [20, 150, 135]
    orange = [255, 90, 0]

class GlucoseItem:
    def __init__(self, type: str, glucose: int, dateString, direction : str = None):
        self.type = type
        self.glucose = glucose
        self.dateString = dateString 
        self.direction = direction

class TreatmentItem:
    def __init__(self, type, dateString, amount):
        self.type = type
        self.date = dateString
        self.amount = int(amount)

class ExerciseItem:
    def __init__(self, type, dateString, amount):
        self.type = type
        self.date = dateString
        self.amount = int(amount)

if __name__ == "__main__":
    GlucoseMatrixDisplay().run_command_in_loop()
