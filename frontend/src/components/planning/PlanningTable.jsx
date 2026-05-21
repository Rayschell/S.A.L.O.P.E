import PlanningLegend from './PlanningLegend.jsx'
import '../../styles/planning.css'

export default function PlanningTable({ slots, members, assignments }) {
  const getAssignment = (memberId, slotId) =>
    assignments.find((a) => a.memberId === memberId && a.slotId === slotId)

  const slotTotals = slots.map((slot) => ({
    slotId: slot.id,
    total: assignments.filter((a) => a.slotId === slot.id).length,
  }))

  return (
    <div>
      <div className="planning-wrapper">
        <div style={{ overflowX: 'auto' }}>
          <table className="planning-table">
            <thead>
              <tr>
                <th>Membre</th>
                {slots.map((slot) => (
                  <th key={slot.id}>{slot.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id}>
                  <td>
                    {member.name}
                    {member.isBureau && <span className="bureau-dot" title="Bureau" />}
                  </td>
                  {slots.map((slot) => {
                    const asg = getAssignment(member.id, slot.id)
                    let cls = ''
                    let label = ''
                    if (asg?.type === 'staff') { cls = 'cell-staff'; label = 'S' }
                    else if (asg?.type === 'respo_bar') { cls = 'cell-respo'; label = 'R' }
                    return (
                      <td key={slot.id} className={cls}>{label}</td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Total staffés</td>
                {slotTotals.map(({ slotId, total }) => (
                  <td key={slotId}>{total}</td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
      <PlanningLegend />
    </div>
  )
}
