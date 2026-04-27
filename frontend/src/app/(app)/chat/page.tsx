import type {Metadata} from "next";
import ChatPage from "./chat-client";

export const metadata: Metadata = {
    robots: {index: false, follow: false},
};

export default ChatPage;
