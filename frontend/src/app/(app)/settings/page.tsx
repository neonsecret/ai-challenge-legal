import type {Metadata} from "next";
import SettingsPage from "./settings-client";

export const metadata: Metadata = {
    robots: {index: false, follow: false},
};

export default SettingsPage;
