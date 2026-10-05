class HuntCycle {
  constructor(map, zone, repopSeconds) {
    this.map = map;
    this.zone = zone;
    this.repopSeconds = repopSeconds;
    this.phase = 'entering';
    this.visit = null;
    this.cursor = 0;
    this.deadline = null;
  }
  decide(adventure, now, player) {
    if (!Number.isFinite(now)) throw new Error('Horloge de jeu absente du client');
    if (adventure.field_map === this.map) {
      if (this.phase === 'waiting') this.phase = 'leaving';
      if (this.phase === 'leaving') return {type:'exit',destination:this.outside};
      if (this.visit !== adventure.encounter_number) {
        this.visit = adventure.encounter_number;
        this.cursor = 0;
        this.phase = 'hunting';
      }
      const unit = adventure.battle.players[player];
      const points = adventure.battle.map.spawns || [];
      while (this.cursor < points.length && Math.hypot(...points[this.cursor].map((n,i)=>n-unit.position[i])) <= 1.5) this.cursor++;
      if (this.cursor < points.length) return {type:'walk',point:points[this.cursor]};
      const exits = adventure.battle.map.exits || [];
      const gate = exits.find(g=>g.destination===this.zone && g.destination!==this.map) || exits.find(g=>g.destination!==this.map);
      if (!gate) throw new Error(`Aucune sortie pour attendre le repop de ${this.map}`);
      this.outside = gate.destination;
      this.phase = 'leaving';
      return {type:'exit',destination:this.outside};
    }
    if (this.phase === 'leaving') {
      this.phase = 'waiting';
      this.deadline = now + this.repopSeconds + 3;
    }
    if (this.phase === 'waiting') {
      if (now < this.deadline) return {type:'wait',remaining:this.deadline-now};
      this.phase = 'returning';
    }
    return {type:'enter',destination:this.map};
  }
}
module.exports = {HuntCycle};
