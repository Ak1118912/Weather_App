import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                               QTextEdit, QMessageBox, QProgressBar, QComboBox,
                               QGroupBox, QGridLayout, QFrame)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl, QRunnable, QThreadPool, Signal, QObject, Slot, QTimer
from PySide6.QtGui import QPixmap, QFont, QPalette

class WeatherCache:
    """
    Simple caching mechanism for weather data
    """
    def __init__(self, ttl_minutes: int = 30):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    def get(self, city: str) -> Optional[Dict[str, Any]]:
        """Get cached weather data if still valid"""
        if city.lower() in self.cache:
            entry = self.cache[city.lower()]
            if datetime.now() < entry['expiry']:
                return entry['data']
            else:
                del self.cache[city.lower()]
        return None

    def set(self, city: str, data: Dict[str, Any]) -> None:
        """Cache weather data with expiry time"""
        self.cache[city.lower()] = {
            'data': data,
            'expiry': datetime.now() + self.ttl
        }

class APIErrorHandler:
    """
    Centralized error handling for OpenWeatherMap API responses
    """
    ERROR_CODES = {
        200: "Success",
        400: "Bad Request - Invalid request parameters",
        401: "Unauthorized - Invalid API key",
        403: "Forbidden - API key blocked",
        404: "Not Found - City not found",
        429: "Too Many Requests - Rate limit exceeded",
        500: "Internal Server Error - Server error",
        502: "Bad Gateway - Server temporarily unavailable",
        503: "Service Unavailable - Service temporarily unavailable"
    }

    @classmethod
    def get_error_message(cls, status_code: int, response_text: str = "") -> str:
        """Get user-friendly error message for HTTP status code"""
        base_message = cls.ERROR_CODES.get(status_code, f"Unknown error (Code: {status_code})")

        try:
            if response_text:
                data = json.loads(response_text)
                if 'message' in data:
                    return f"{base_message}: {data['message']}"
        except json.JSONDecodeError:
            pass

        return base_message

class WeatherAPI:
    """
    OpenWeatherMap API wrapper with proper error handling and caching
    """
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
    ICON_BASE_URL = "http://openweathermap.org/img/wn/"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.cache = WeatherCache()
        self.session = requests.Session()
        self.session.timeout = 10

    def get_weather(self, city: str, units: str = 'metric') -> Dict[str, Any]:
        """
        Get weather data for a city with caching and error handling
        """
        cached_data = self.cache.get(city)
        if cached_data:
            cached_data['from_cache'] = True
            return cached_data

        params = {
            'q': city,
            'appid': self.api_key,
            'units': units
        }

        response = self.session.get(self.BASE_URL, params=params)

        if response.status_code == 200:
            data = response.json()
            data['from_cache'] = False
            # Cache the successful response
            self.cache.set(city, data)
            return data
        else:
            error_msg = APIErrorHandler.get_error_message(response.status_code, response.text)
            raise requests.exceptions.HTTPError(error_msg)

class EnhancedWorkerSignals(QObject):
    """
    Enhanced signals for better communication between threads
    """
    finished = Signal()
    error = Signal(str)
    result = Signal(dict)
    progress = Signal(int)
    status_update = Signal(str)

class EnhancedWeatherWorker(QRunnable):
    """
    Enhanced worker thread with better error handling and status updates
    """

    def __init__(self, city: str, api_key: str, units: str = 'metric'):
        super().__init__()
        self.city = city
        self.api_key = api_key
        self.units = units
        self.signals = EnhancedWorkerSignals()
        self.weather_api = WeatherAPI(api_key)

    @Slot()
    def run(self):
        """
        Execute the weather API request with enhanced error handling
        """
        try:
            self.signals.status_update.emit("Initializing request...")
            self.signals.progress.emit(10)

            self.signals.status_update.emit("Checking cache...")
            self.signals.progress.emit(25)

            self.signals.status_update.emit("Fetching weather data...")
            self.signals.progress.emit(50)

            # Get weather data
            weather_data = self.weather_api.get_weather(self.city, self.units)

            self.signals.progress.emit(90)
            self.signals.status_update.emit("Processing data...")

            # Add timestamp for display
            weather_data['retrieved_at'] = datetime.now().isoformat()

            self.signals.progress.emit(100)
            self.signals.status_update.emit("Complete!")
            self.signals.result.emit(weather_data)

        except requests.exceptions.Timeout:
            self.signals.error.emit("Request timed out. Please check your internet connection and try again.")
        except requests.exceptions.ConnectionError:
            self.signals.error.emit("Unable to connect to weather service. Please check your internet connection.")
        except requests.exceptions.HTTPError as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"Unexpected error: {str(e)}")
        finally:
            self.signals.finished.emit()

class EnhancedWeatherApp(QMainWindow):
    """
    Enhanced weather application with better UI and features
    """

    def __init__(self):
        super().__init__()
        self.api_key = "YOUR_API_key"  # Replace with your actual API key
        self.thread_pool = QThreadPool()
        self.current_worker = None
        self.init_ui()
        self.setup_styles()

    def init_ui(self):
        """
        Initialize the enhanced user interface
        """
        self.setWindowTitle("Enhanced Weather App - OpenWeatherMap Integration")
        self.setFixedSize(700, 600)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Header section
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Box)
        header_layout = QVBoxLayout()
        header_frame.setLayout(header_layout)

        title_label = QLabel("Weather Information Dashboard")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        main_layout.addWidget(header_frame)

        # Input section
        input_group = QGroupBox("Search")
        input_layout = QGridLayout()
        input_group.setLayout(input_layout)

        # City input
        input_layout.addWidget(QLabel("City:"), 0, 0)
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Enter city name (e.g., London, New York)")
        self.city_input.returnPressed.connect(self.get_weather)
        input_layout.addWidget(self.city_input, 0, 1)

        # Units selection
        input_layout.addWidget(QLabel("Units:"), 1, 0)
        self.units_combo = QComboBox()
        self.units_combo.addItems(["metric (°C)", "imperial (°F)", "kelvin (K)"])
        input_layout.addWidget(self.units_combo, 1, 1)

        # Search button
        self.search_button = QPushButton("Get Weather")
        self.search_button.clicked.connect(self.get_weather)
        input_layout.addWidget(self.search_button, 2, 0, 1, 2)

        main_layout.addWidget(input_group)

        # Progress section
        progress_group = QGroupBox("Status")
        progress_layout = QVBoxLayout()
        progress_group.setLayout(progress_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)

        main_layout.addWidget(progress_group)

        # Weather display section
        display_group = QGroupBox("Weather Data")
        display_layout = QVBoxLayout()
        display_group.setLayout(display_layout)

        self.weather_display = QTextEdit()
        self.weather_display.setReadOnly(True)
        display_layout.addWidget(self.weather_display)

        main_layout.addWidget(display_group)

    def setup_styles(self):
        """
        Apply custom styles to the application
        """
        style_sheet = """
        QGroupBox {
            font-weight: bold;
            border: 2px solid gray;
            border-radius: 5px;
            margin: 5px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:disabled {
            background-color: #cccccc;
        }
        QTextEdit {
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 5px;
            font-family: 'Courier New', monospace;
        }
        """
        self.setStyleSheet(style_sheet)

    def get_weather(self):
        """
        Initiate weather data fetching with enhanced validation
        """
        city = self.city_input.text().strip()

        if not city:
            QMessageBox.warning(self, "Input Error", "Please enter a city name.")
            return

        if len(city) < 2:
            QMessageBox.warning(self, "Input Error", "City name must be at least 2 characters long.")
            return

        if not self.api_key or self.api_key == "YOUR_Alternate_API_key":
            QMessageBox.critical(self, "Configuration Error", 
                               "Please set your OpenWeatherMap API key in the code.\n\n"
                               "Get your free API key at: https://openweathermap.org/api")
            return

        # Get selected units
        units_map = {"metric (°C)": "metric", "imperial (°F)": "imperial", "kelvin (K)": "kelvin"}
        units = units_map[self.units_combo.currentText()]

        # Disable button and show progress
        self.search_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Searching for {city}...")

        # Create and start worker thread
        self.current_worker = EnhancedWeatherWorker(city, self.api_key, units)
        self.current_worker.signals.result.connect(self.handle_weather_result)
        self.current_worker.signals.error.connect(self.handle_error)
        self.current_worker.signals.finished.connect(self.handle_finished)
        self.current_worker.signals.progress.connect(self.progress_bar.setValue)
        self.current_worker.signals.status_update.connect(self.status_label.setText)

        self.thread_pool.start(self.current_worker)

    def handle_weather_result(self, weather_data):
        """
        Handle successful weather data retrieval with enhanced formatting
        """
        try:
            # Extract information
            city_name = weather_data['name']
            country = weather_data['sys']['country']
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            humidity = weather_data['main']['humidity']
            pressure = weather_data['main']['pressure']
            description = weather_data['weather'][0]['description'].title()
            wind_speed = weather_data['wind']['speed']
            visibility = weather_data.get('visibility', 'N/A')

            # Get unit symbols
            units = self.units_combo.currentText()
            if "metric" in units:
                temp_unit, speed_unit = "°C", "m/s"
            elif "imperial" in units:
                temp_unit, speed_unit = "°F", "mph"
            else:
                temp_unit, speed_unit = "K", "m/s"

            # Check if data is from cache
            cache_info = "✓ From cache" if weather_data.get('from_cache', False) else "✓ Fresh data"

            # Format the weather information
            weather_info = f"""
📍 LOCATION: {city_name}, {country}
📊 DATA STATUS: {cache_info}
⏰ RETRIEVED: {datetime.fromisoformat(weather_data['retrieved_at']).strftime('%Y-%m-%d %H:%M:%S')}

🌡️  TEMPERATURE
   Current: {temp}{temp_unit}
   Feels like: {feels_like}{temp_unit}

🌤️  CONDITIONS
   Weather: {description}

💨 ATMOSPHERIC DATA
   Humidity: {humidity}%
   Pressure: {pressure} hPa
   Wind Speed: {wind_speed} {speed_unit}
   Visibility: {visibility/1000 if isinstance(visibility, (int, float)) else visibility} km

🗺️  COORDINATES
   Latitude: {weather_data['coord']['lat']}°
   Longitude: {weather_data['coord']['lon']}°

🔗 ICON CODE: {weather_data['weather'][0]['icon']}
            """

            self.weather_display.setPlainText(weather_info.strip())
            self.status_label.setText("Weather data retrieved successfully!")

        except KeyError as e:
            self.handle_error(f"Error parsing weather data: Missing key {e}")

    def handle_error(self, error_message):
        """
        Handle errors with user-friendly display
        """
        error_display = f"""
❌ ERROR OCCURRED

{error_message}

💡 TROUBLESHOOTING TIPS:
• Check your internet connection
• Verify the city name is spelled correctly
• Ensure your API key is valid and active
• Try again in a few moments if rate limited

🔗 Get API key at: https://openweathermap.org/api
        """

        self.weather_display.setPlainText(error_display.strip())
        self.status_label.setText("Error occurred - see details above")

    def handle_finished(self):
        """
        Handle completion of weather data request
        """
        self.search_button.setEnabled(True)
        self.progress_bar.setVisible(False)

def main():
    """
    Main application entry point
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern looking style

    # Set application properties
    app.setApplicationName("Enhanced Weather App")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Weather Apps Inc.")

    window = EnhancedWeatherApp()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
