import logging
import httpx
from typing import List, Dict, Any, Optional
from .config import API_BASE_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class EventsApiClient:
    """
    Async client for communicating with University Events Hub REST API.
    The bot interacts with Django solely via these endpoints.
    """

    def __init__(self, base_url: str = API_BASE_URL, timeout: float = REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    async def get_events(
        self,
        range_type: Optional[str] = None,
        category: Optional[Any] = None,
        club: Optional[Any] = None,
        status: Optional[str] = None,
        telegram_admin_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events matching filters (e.g. range=today, range=week, category=1).
        """
        params = {}
        if range_type:
            params['range'] = range_type
        if category:
            params['category'] = category
        if club:
            params['club'] = club
        if status:
            params['status'] = status

        headers = {}
        if telegram_admin_id:
            headers['X-Telegram-User-Id'] = str(telegram_admin_id)

        url = f"{self.base_url}/events/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error fetching events from %s: %s", url, e)
            raise

    async def get_event_detail(self, event_id: int) -> Dict[str, Any]:
        """
        Fetch a single event's full details.
        """
        url = f"{self.base_url}/events/{event_id}/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error fetching event %d: %s", event_id, e)
            raise

    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a new event (status is set to pending by backend).
        """
        url = f"{self.base_url}/events/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=event_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error creating event: %s", e)
            raise

    async def update_event_status(
        self,
        event_id: int,
        status_value: str,
        admin_telegram_id: int,
        channel_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Admin action to approve, reject, or cancel an event.
        """
        url = f"{self.base_url}/events/{event_id}/status/"
        payload = {"status": status_value}
        if channel_message_id is not None:
            payload["channel_message_id"] = channel_message_id

        headers = {"X-Telegram-User-Id": str(admin_telegram_id)}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error updating status for event %d: %s", event_id, e)
            raise

    async def update_event_structured_fields(
        self,
        event_id: int,
        fields: Dict[str, Any],
        admin_telegram_id: int,
    ) -> Dict[str, Any]:
        """
        Admin action to update structured queryable fields of an event.
        """
        url = f"{self.base_url}/events/{event_id}/"
        headers = {"X-Telegram-User-Id": str(admin_telegram_id)}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(url, json=fields, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error updating fields for event %d: %s", event_id, e)
            raise

    async def get_categories(self) -> List[Dict[str, Any]]:
        """
        Fetch all event categories.
        """
        url = f"{self.base_url}/categories/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error fetching categories: %s", e)
            raise

    async def get_clubs(self) -> List[Dict[str, Any]]:
        """
        Fetch all registered clubs.
        """
        url = f"{self.base_url}/clubs/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error fetching clubs: %s", e)
            raise

    async def add_club_officer(
        self,
        club_id: int,
        officer_telegram_id: int,
        admin_telegram_id: int,
    ) -> Dict[str, Any]:
        """
        Admin action to add a verified Telegram officer to a club.
        """
        url = f"{self.base_url}/clubs/{club_id}/officers/"
        payload = {"telegram_id": officer_telegram_id}
        headers = {"X-Telegram-User-Id": str(admin_telegram_id)}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error adding officer to club %d: %s", club_id, e)
            raise

    async def remove_club_officer(
        self,
        club_id: int,
        officer_telegram_id: int,
        admin_telegram_id: int,
    ) -> Dict[str, Any]:
        """
        Admin action to remove a verified Telegram officer from a club.
        """
        url = f"{self.base_url}/clubs/{club_id}/officers/"
        payload = {"telegram_id": officer_telegram_id}
        headers = {"X-Telegram-User-Id": str(admin_telegram_id)}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("API error removing officer from club %d: %s", club_id, e)
            raise


# Global singleton instance
api_client = EventsApiClient()
