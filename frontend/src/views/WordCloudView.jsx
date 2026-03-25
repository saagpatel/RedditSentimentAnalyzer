import * as d3 from "d3";
import cloud from "d3-cloud";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTerms } from "../api/client";

function sentimentColor(compound) {
	if (compound > 0.1) return "#3b82f6";
	if (compound < -0.1) return "#ef4444";
	return "#6b7280";
}

export default function WordCloudView({ subreddit, timeRange }) {
	const svgRef = useRef(null);
	const tooltipRef = useRef(null);
	const [terms, setTerms] = useState([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);

	const loadTerms = useCallback(async () => {
		if (!subreddit) return;
		setLoading(true);
		setError(null);
		try {
			const result = await fetchTerms(
				subreddit,
				timeRange.start,
				timeRange.end,
				50,
			);
			setTerms(result.terms || []);
		} catch (err) {
			setError(err.message);
			setTerms([]);
		} finally {
			setLoading(false);
		}
	}, [subreddit, timeRange]);

	useEffect(() => {
		loadTerms();
	}, [loadTerms]);

	useEffect(() => {
		if (!terms.length || !svgRef.current) return;

		const width = 800;
		const height = 450;
		const maxCount = Math.max(...terms.map((t) => t.count));
		const minCount = Math.min(...terms.map((t) => t.count));

		const sizeScale = d3
			.scaleLinear()
			.domain([minCount, maxCount])
			.range([14, 60]);

		const words = terms.map((t) => ({
			text: t.term,
			size: sizeScale(t.count),
			count: t.count,
			compound: t.avg_compound,
		}));

		const layout = cloud()
			.size([width, height])
			.words(words)
			.padding(4)
			.rotate(() => (Math.random() > 0.7 ? 90 : 0))
			.fontSize((d) => d.size)
			.on("end", draw);

		layout.start();

		function draw(placed) {
			const svg = d3.select(svgRef.current);
			svg.selectAll("*").remove();

			const g = svg
				.attr("width", width)
				.attr("height", height)
				.append("g")
				.attr("transform", `translate(${width / 2},${height / 2})`);

			const tooltip = d3.select(tooltipRef.current);

			g.selectAll("text")
				.data(placed)
				.enter()
				.append("text")
				.style("font-size", (d) => `${d.size}px`)
				.style("font-family", "inherit")
				.style("font-weight", "700")
				.style("fill", (d) => sentimentColor(d.compound))
				.style("cursor", "default")
				.style("transition", "opacity 150ms ease")
				.attr("text-anchor", "middle")
				.attr(
					"transform",
					(d) => `translate(${d.x},${d.y}) rotate(${d.rotate})`,
				)
				.text((d) => d.text)
				.on("mouseover", (event, d) => {
					tooltip
						.style("opacity", 1)
						.style("left", `${event.pageX + 12}px`)
						.style("top", `${event.pageY - 10}px`)
						.html(
							`<strong>${d.text}</strong><br/>` +
								`Count: ${d.count}<br/>` +
								`Avg sentiment: ${d.compound.toFixed(3)}`,
						);
				})
				.on("mouseout", () => {
					tooltip.style("opacity", 0);
				});
		}
	}, [terms]);

	if (loading) {
		return <div className="chart-placeholder">Loading word cloud...</div>;
	}

	if (error) {
		return <div className="chart-placeholder error">Error: {error}</div>;
	}

	if (!terms.length) {
		return (
			<div className="chart-placeholder">
				No term data available for this range.
			</div>
		);
	}

	return (
		<div className="chart-container">
			<h2>Top Terms &mdash; r/{subreddit}</h2>
			<div className="wordcloud-wrapper">
				<svg ref={svgRef} />
				<div ref={tooltipRef} className="wordcloud-tooltip" />
			</div>
		</div>
	);
}
