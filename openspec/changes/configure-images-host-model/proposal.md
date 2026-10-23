# Configure the Images host model

Image generation fails before reaching upstream when the account catalog does not offer the hardcoded `gpt-5.5` host. Allow the deployment to select its Responses host separately from the public image renderer, using `CODEX_LB_IMAGES_HOST_MODEL`, with `gpt-6-astra` as the current default. Preserve public model policy, accounting, endpoint aliases and image parameters.
