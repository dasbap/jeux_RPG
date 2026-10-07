import asyncio
from .service import GameError


class DiscordAdapter:
    def __init__(self, service):
        self.service = service

    def _execute(self, interaction, action, params, class_name):
        if interaction.guild_id is None:
            raise GameError("guild_required", "Utilisez cette commande dans un serveur Discord.")
        with self.service._lock:
            token = self.service._bind_discord(str(interaction.guild_id), str(interaction.user.id),
                                              interaction.user.display_name, class_name)
            if action == "state":
                if set(params) - {"session_id"}:
                    raise GameError("invalid_command", "Paramètres invalides.")
                return self.service.state(token, params.get("session_id"))
            return self.service.command(token, str(interaction.id), action, **params)

    async def execute(self, interaction, action, params=None, class_name="Knight"):
        return await asyncio.to_thread(self._execute, interaction, action, params or {}, class_name)
