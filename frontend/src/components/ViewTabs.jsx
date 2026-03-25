const TABS = [
	{ key: "trend", label: "Trend" },
	{ key: "compare", label: "Compare" },
	{ key: "wordcloud", label: "Words" },
];

export default function ViewTabs({ active, onChange }) {
	return (
		<div className="view-tabs">
			{TABS.map((tab) => (
				<button
					key={tab.key}
					className={active === tab.key ? "active" : ""}
					onClick={() => onChange(tab.key)}
				>
					{tab.label}
				</button>
			))}
		</div>
	);
}
