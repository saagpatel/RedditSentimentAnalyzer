const PRESETS = [
	{ label: "24h", hours: 24 },
	{ label: "7d", hours: 168 },
	{ label: "30d", hours: 720 },
];

export default function TimeRangePicker({ activeLabel, onChange }) {
	function handleClick(preset) {
		const now = Math.floor(Date.now() / 1000);
		onChange({
			start: now - preset.hours * 3600,
			end: now,
			label: preset.label,
		});
	}

	return (
		<div className="time-range-picker">
			{PRESETS.map((p) => (
				<button
					key={p.label}
					onClick={() => handleClick(p)}
					className={activeLabel === p.label ? "active" : ""}
				>
					{p.label}
				</button>
			))}
		</div>
	);
}
