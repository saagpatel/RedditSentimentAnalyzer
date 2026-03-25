import { useEffect, useState } from "react";
import { fetchTopPosts } from "../api/client";
import SentimentBadge from "./SentimentBadge";

const BUCKET_SECONDS = 21600; // 6 hours

function formatTimestamp(ts) {
	return new Date(ts * 1000).toLocaleString("en-US", {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

export default function SpikeDetailPanel({ spike, subreddit, onClose }) {
	const [posts, setPosts] = useState([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		if (!spike || !subreddit) return;
		setLoading(true);
		fetchTopPosts(
			subreddit,
			spike.bucket_start,
			spike.bucket_start + BUCKET_SECONDS,
			10,
			"compound",
		)
			.then((data) => setPosts(data.posts || []))
			.catch(() => setPosts([]))
			.finally(() => setLoading(false));
	}, [spike, subreddit]);

	if (!spike) return null;

	return (
		<div className="spike-panel-overlay" onClick={onClose}>
			<div className="spike-panel" onClick={(e) => e.stopPropagation()}>
				<div className="spike-panel-header">
					<h3>Spike Investigation</h3>
					<button className="spike-panel-close" onClick={onClose}>
						&times;
					</button>
				</div>

				<div className="spike-panel-meta">
					<span className="spike-panel-time">
						{formatTimestamp(spike.bucket_start)}
					</span>
					<span className="spike-panel-delta">
						Compound: {spike.avg_compound?.toFixed(3) ?? "N/A"}
					</span>
					<span className="spike-panel-count">
						{spike.post_count} posts &middot; {spike.comment_count} comments
					</span>
				</div>

				<h4>Top Posts in Window</h4>

				{loading ? (
					<p className="spike-panel-loading">Loading posts...</p>
				) : posts.length === 0 ? (
					<p className="spike-panel-loading">No posts found in this window.</p>
				) : (
					<ul className="spike-post-list">
						{posts.map((post) => (
							<li key={post.id} className="spike-post-item">
								<a
									href={post.url}
									target="_blank"
									rel="noopener noreferrer"
									className="spike-post-title"
								>
									{post.title}
								</a>
								<div className="spike-post-meta">
									<SentimentBadge
										compound={post.vader_compound}
										sentimentSource={post.sentiment_source}
										llmSentiment={post.llm_sentiment}
										llmReasoning={post.llm_reasoning}
									/>
									<span>{post.score} pts</span>
									<span>{(post.upvote_ratio * 100).toFixed(0)}% upvoted</span>
								</div>
							</li>
						))}
					</ul>
				)}
			</div>
		</div>
	);
}
