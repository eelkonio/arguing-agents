import { useState, useRef, useEffect } from "react";

interface TruncatedTopicProps {
  topic: string;
  maxLength?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function TruncatedTopic({
  topic,
  maxLength = 300,
  className,
  style,
}: TruncatedTopicProps) {
  const [showPopup, setShowPopup] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const isTruncated = topic.length > maxLength;
  const displayText = isTruncated ? topic.slice(0, maxLength) + "…" : topic;

  useEffect(() => {
    if (!showPopup) return;
    function handleClickOutside(e: MouseEvent) {
      if (
        ref.current &&
        !ref.current.contains(e.target as Node) &&
        popupRef.current &&
        !popupRef.current.contains(e.target as Node)
      ) {
        setShowPopup(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showPopup]);

  if (!isTruncated) {
    return (
      <span className={className} style={style}>
        {topic}
      </span>
    );
  }

  return (
    <span
      ref={ref}
      className={className}
      style={{ ...style, position: "relative", cursor: "pointer" }}
      onMouseEnter={() => setShowPopup(true)}
      onMouseLeave={() => setShowPopup(false)}
    >
      {displayText}
      {showPopup && (
        <div
          ref={popupRef}
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            zIndex: 1000,
            maxWidth: 600,
            padding: "12px 16px",
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: 8,
            color: "#e1e4e8",
            fontSize: "14px",
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            marginTop: 4,
          }}
          onMouseEnter={() => setShowPopup(true)}
          onMouseLeave={() => setShowPopup(false)}
        >
          {topic}
        </div>
      )}
    </span>
  );
}
