import { useEffect, useState } from "react";
import { fetchHealth } from "../api/client";

export default function SubredditSelector({ value, onChange }) {
	const [subreddits, setSubreddits] = useState([]);

	useEffect(() => {
		fetchHealth()
			.then((data) => {
				setSubreddits(data.tracked_subreddits || []);
				if (!value && data.tracked_subreddits?.length > 0) {
					onChange(data.tracked_subreddits[0]);
				}
			})
			.catch((err) => console.error("Failed to load subreddits:", err));
	}, []);

	return (
		<select
			value={value || ""}
			onChange={(e) => onChange(e.target.value)}
			className="subreddit-selector"
		>
			{subreddits.map((name) => (
				<option key={name} value={name}>
					r/{name}
				</option>
			))}
		</select>
	);
}
