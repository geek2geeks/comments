from services.avatar_service import AvatarService
from services.connection_service import ConnectionService

avatar_service = AvatarService()
connection_service = ConnectionService()


def get_avatar_service() -> AvatarService:
    return avatar_service


def get_connection_service() -> ConnectionService:
    return connection_service
