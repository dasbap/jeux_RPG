"""Builder editing of conversations, individual subjects, answers and clues."""

from copy import deepcopy


def rows(project):
    story = project.content.get("narrative")
    if not story:
        return []
    names = {
        site["id"]: site["name"]
        for data in project.maps.values()
        for site in data["sites"]
    }
    result = [("title", story["title"], "Titre de l’histoire")]
    for npc, value in story["npcs"].items():
        result.append(
            ("npc|" + npc, names.get(npc, npc), "Accueil : " + value["greeting"])
        )
        for topic in value["topics"]:
            result.append(
                (
                    f"topic|{npc}|{topic['id']}",
                    topic["label"],
                    f"Sujet de {npc} · {topic['text']}",
                )
            )
            for answer in topic.get("choices", []):
                result.append(
                    (
                        f"answer|{npc}|{topic['id']}|{answer['id']}",
                        answer["label"],
                        f"Réponse · {npc} / {topic['label']}",
                    )
                )
    result.extend(
        ("fact|" + key, value["name"], f"Indice · {value['map']} / {value['npc']}")
        for key, value in story["facts"].items()
    )
    return result


def locate(story, key):
    parts = key.split("|")
    if key == "title":
        return story, "title"
    if parts[0] in ("npc", "fact"):
        return story["npcs" if parts[0] == "npc" else "facts"], parts[1]
    topics = story["npcs"][parts[1]]["topics"]
    if parts[0] == "topic":
        return topics, next(
            i for i, topic in enumerate(topics) if topic["id"] == parts[2]
        )
    answers = next(topic for topic in topics if topic["id"] == parts[2])["choices"]
    return answers, next(
        i for i, answer in enumerate(answers) if answer["id"] == parts[3]
    )


class ControllerNarrativeMixin:
    def inspect_narrative(self):
        selection = self.tables["narrative"].selection()
        if selection:
            container, key = locate(self.project.content["narrative"], selection[0])
            self.show_report("Histoire / dialogues / indices", container[key])

    def edit_narrative(self, new=False):
        p = self.project
        selected = self.tables["narrative"].selection()
        if not new and not selected:
            return
        before = p.state()
        try:
            story = p.content.setdefault(
                "narrative", {"title": "Nouvelle histoire", "facts": {}, "npcs": {}}
            )
            sites = {
                site["id"]: site for data in p.maps.values() for site in data["sites"]
            }
            if new:
                if not self._create_narrative(story, sites):
                    p.restore(before)
                    return
            else:
                container, key = locate(story, selected[0])
                old = container[key]
                if selected[0] == "title":
                    values = self.form("Titre de l’histoire", {"title": old})
                    if values is None:
                        return
                    container[key] = values["title"]
                else:
                    hidden = {"topics", "choices"}
                    values = self.form(
                        "Histoire : " + selected[0],
                        {k: deepcopy(v) for k, v in old.items() if k not in hidden},
                        {
                            "map": list(p.maps),
                            "npc": list(sites),
                            "service": ["", "forge"],
                        },
                    )
                    if values is None:
                        return
                    container[key] = {
                        **values,
                        **{k: deepcopy(v) for k, v in old.items() if k in hidden},
                    }
            for data in p.maps.values():
                for site in data["sites"]:
                    if site["id"] in story["npcs"]:
                        site["dialogue"] = story["npcs"][site["id"]]["greeting"]
            p.validate()
            self.remember(before)
            self.refresh()
        except (ValueError, KeyError, TypeError) as exc:
            p.restore(before)
            self.messagebox.showerror("Histoire", str(exc), parent=self.root)

    def delete_narrative(self):
        selected = self.tables["narrative"].selection()
        if not selected or selected[0] == "title":
            return
        if not self.messagebox.askyesno(
            "Supprimer",
            "Supprimer cet élément narratif ? Les références utilisées seront vérifiées.",
            parent=self.root,
        ):
            return
        before = self.project.state()
        try:
            container, key = locate(self.project.content["narrative"], selected[0])
            container.pop(key)
            self.finish_change(before)
        except (ValueError, KeyError, TypeError) as exc:
            self.project.restore(before)
            self.messagebox.showerror("Histoire", str(exc), parent=self.root)

    def _create_narrative(self, story, sites):
        p = self.project
        mode = self.form(
            "Nouveau contenu d’histoire",
            {"record": "npc"},
            {"record": ["npc", "topic", "answer", "fact"]},
        )
        if mode is None:
            return False
        kind = mode["record"]
        if kind == "npc":
            values = self.form(
                "Conversation",
                {
                    "npc": next(iter(sites)),
                    "greeting": "Bonjour, voyageur.",
                    "service": "",
                    "greetings": [],
                },
                {"npc": list(sites), "service": ["", "forge"]},
            )
            if values is None:
                return False
            npc = values.pop("npc")
            if npc in story["npcs"]:
                raise ValueError(
                    "Cette conversation existe déjà. Modifiez son accueil ou ajoutez un sujet."
                )
            story["npcs"][npc] = {**values, "topics": []}
        elif kind == "fact":
            values = self.form(
                "Indice",
                {
                    "id": "nouvel_indice",
                    "name": "Nouvel indice",
                    "description": "Texte de la note conservée dans le journal.",
                    "map": next(iter(p.maps)),
                    "npc": next(iter(sites)),
                },
                {"map": list(p.maps), "npc": list(sites)},
            )
            if values is None:
                return False
            key = values.pop("id")
            if key in story["facts"]:
                raise ValueError("Cet indice existe déjà.")
            story["facts"][key] = values
        else:
            parents = (
                list(story["npcs"])
                if kind == "topic"
                else [
                    f"{npc}|{topic['id']}"
                    for npc, value in story["npcs"].items()
                    for topic in value["topics"]
                ]
            )
            if not parents:
                raise ValueError("Créez d’abord une conversation et un sujet.")
            parent = self.form(
                "Emplacement", {"parent": parents[0]}, {"parent": parents}
            )
            if parent is None:
                return False
            if kind == "topic":
                container = story["npcs"][parent["parent"]]["topics"]
            else:
                npc, key = parent["parent"].split("|")
                container = next(
                    topic
                    for topic in story["npcs"][npc]["topics"]
                    if topic["id"] == key
                ).setdefault("choices", [])
            initial = {
                "id": "nouveau_sujet" if kind == "topic" else "nouvelle_reponse",
                "label": "Nouveau sujet" if kind == "topic" else "Nouvelle réponse",
                "text": "Texte du dialogue.",
                "requires": [],
                "requires_facts": [],
                "facts": [],
            }
            if kind == "answer":
                initial["description"] = ""
            values = self.form("Sujet" if kind == "topic" else "Réponse", initial)
            if values is None:
                return False
            container.append(values)
        return True
