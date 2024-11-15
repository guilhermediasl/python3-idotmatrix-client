from datetime import datetime

class Color:
    red = [255, 20, 10]
    green = [70, 167, 10]
    yellow = [244, 170, 0]
    purple = [250, 0, 105]
    white = [230, 170, 80]
    blue = [25, 150, 125]
    orange = [245, 70, 0]

class GlucoseItem:
    def __init__(self, type: str, glucose: int, date, direction : str = None):
        self.type = type
        self.glucose = glucose
        self.date = date 
        self.direction = direction

class TreatmentItem:
    def __init__(self,id: str, type: str, date: datetime, amount: int):
        self.id: str = id
        self.type: str = type
        self.date: datetime = date
        self.amount: int = int(amount)

    def __str__(self):
        return f"TreatmentItem(type='{self.type}', date='{self.date}', amount={self.amount})"

    def __repr__(self):
        return self.__str__()

class ExerciseItem:
    def __init__(self, type, dateString, amount):
        self.type = type
        self.date = dateString
        self.amount = int(amount)

    def __str__(self):
        return f"ExerciseItem (type='{self.type}', date='{self.date}', amount={self.amount})"

    def __repr__(self):
        return self.__str__()