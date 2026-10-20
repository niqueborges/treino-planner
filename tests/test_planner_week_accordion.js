const fs = require('fs');
const source = fs.readFileSync(require('path').join(__dirname, '..', 'app.js'), 'utf8');
const match = source.match(/function nextExpandedPlannerDay\(activeWeekday,actionWeekday,action\)\{[^}]+\}/);
if (!match) throw new Error('planner day state helper not found');
const nextExpandedPlannerDay = new Function(`${match[0]}; return nextExpandedPlannerDay;`)();
function assert(condition, message) {
  if (!condition) throw new Error(message);
}

let expandedWeekday = null;
expandedWeekday = nextExpandedPlannerDay(expandedWeekday, 1, 'open');
assert(expandedWeekday === 1, 'opening a day should expand it');
assert([1, 2, 3, 4, 5, 6, 7].filter(weekday => weekday === expandedWeekday).length === 1, 'only one day should be expanded');
expandedWeekday = nextExpandedPlannerDay(expandedWeekday, 4, 'open');
assert(expandedWeekday === 4, 'opening another day should replace the expanded day');
expandedWeekday = nextExpandedPlannerDay(expandedWeekday, 4, 'close');
assert(expandedWeekday === null, 'closing a day should return to the compact week');
assert(source.includes('editor.hidden=activePlannerWeekday!==weekday'), 'the editor should be hidden for every inactive day');
assert(source.includes('`/api/workout-days/${source.id}/duplicate`'), 'day duplication should use the workout day API');
console.log('planner week accordion tests passed');
