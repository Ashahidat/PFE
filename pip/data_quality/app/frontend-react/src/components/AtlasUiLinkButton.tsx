import OpenInNewOutlinedIcon from "@mui/icons-material/OpenInNewOutlined";
import { Button, ButtonProps } from "@mui/material";
import { ATLAS_UI_URL, canOpenAtlasUi } from "../lib/externalLinks";
import { getUserRole } from "../lib/storage";

type AtlasUiLinkButtonProps = ButtonProps<"a"> & {
  label?: string;
};

export default function AtlasUiLinkButton({ label = "Consulter le catalogue", ...props }: AtlasUiLinkButtonProps) {
  if (!canOpenAtlasUi(getUserRole())) return null;

  return (
    <Button
      {...props}
      component="a"
      href={ATLAS_UI_URL}
      target="_blank"
      rel="noopener noreferrer"
      endIcon={<OpenInNewOutlinedIcon />}
    >
      {label}
    </Button>
  );
}
