export default function SentimentBadge({
	compound,
	sentimentSource,
	llmSentiment,
	llmReasoning,
}) {
	if (compound == null && !llmSentiment) return null;

	// LLM-analyzed posts get a distinct purple badge
	if (sentimentSource === "llm" && llmSentiment) {
		return (
			<span className="badge llm" title={llmReasoning || `AI: ${llmSentiment}`}>
				AI: {llmSentiment}
			</span>
		);
	}

	// VADER-scored posts use compound-based badge
	let label, className;
	if (compound >= 0.3) {
		label = "Positive";
		className = "badge positive";
	} else if (compound <= -0.3) {
		label = "Negative";
		className = "badge negative";
	} else {
		label = "Neutral";
		className = "badge neutral";
	}

	return (
		<span className={className} title={`Compound: ${compound.toFixed(3)}`}>
			{label}
		</span>
	);
}
