const PRESETS = [
	{ label: "24h", hours: 24 },
	{ label: "7d", hours: 168 },
	{ label: "30d", hours: 720 },
];

function rangeForPreset(preset, now = Math.floor(Date.now() / 1000)) {
	return {
		start: now - preset.hours * 3600,
		end: now,
		label: preset.label,
	};
}

export default function TimeRangePicker({ activeLabel, onChange }) {
	function handleClick(preset) {
		onChange(rangeForPreset(preset));
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
