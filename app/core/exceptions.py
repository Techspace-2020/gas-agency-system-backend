from fastapi import HTTPException, status

class BusinessException(Exception):
    """Base exception for business logic errors"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class DayAlreadyExistsException(BusinessException):
    def __init__(self, date: str):
        super().__init__(
            f"Stock day already exists for date: {date}",
            status.HTTP_409_CONFLICT
        )

class DayNotOpenException(BusinessException):
    def __init__(self, date: str):
        super().__init__(
            f"Stock day {date} is not in OPEN status",
            status.HTTP_400_BAD_REQUEST
        )

class DayNotFoundException(BusinessException):
    def __init__(self, date: str):
        super().__init__(
            f"Stock day not found for date: {date}",
            status.HTTP_404_NOT_FOUND
        )

class PreviousDayNotClosedException(BusinessException):
    def __init__(self):
        super().__init__(
            "Previous day must be closed before creating new day",
            status.HTTP_400_BAD_REQUEST
        )

class InvalidStockDataException(BusinessException):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY)

class DeliveryBoyNotFoundException(BusinessException):
    def __init__(self, name: str):
        super().__init__(
            f"Delivery boy not found: {name}",
            status.HTTP_404_NOT_FOUND
        )

class NegativeStockException(BusinessException):
    def __init__(self, cylinder_type: str):
        super().__init__(
            f"Stock calculation resulted in negative value for {cylinder_type}",
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )
