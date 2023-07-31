from src.model.CLIP.vpt_clip import VisionPromptCLIP
from src.data.Rice_Image_Dataset.Rice import Rice_Dataset
from src.utils.utils import setup_clip
from torch.utils.data import DataLoader
from tqdm import tqdm
from time import sleep
import numpy as np
import argparse
import clip
import torch
from torch.cuda.amp import autocast



# main function to call from workflow
def main():
    # set up arg parser
    parser = argparse.ArgumentParser(description='Train Vision Prompt CLIP')
    # check cuda availability
    parser.add_argument('--model', type=str, default="ViT-B/32",
                        help='For Saving and loading the current Model')
    parser.add_argument('--device', type=str, default="cuda",
                        help='For Saving and loading the current Model')
    parser.add_argument('--data', type=str, default="Rice_Image_Dataset",
                        help='For Saving and loading the current Model')
    
    args = parser.parse_args()

    # set up cfg and args
    backbone, preprocess, config, prompt_config = setup_clip(args)

    rice_dataset_test = Rice_Dataset(csv_file='src/data/Rice_Image_Dataset/test_meta.csv', root_dir='src/data/Rice_Image_Dataset/', transform=preprocess)
    rice_dataset_train = Rice_Dataset(csv_file='src/data/Rice_Image_Dataset/train_meta.csv', root_dir='src/data/Rice_Image_Dataset/', transform=preprocess)

    # define data loaders
    train_loader, test_loader = DataLoader(rice_dataset_train, batch_size=64, shuffle=True), DataLoader(rice_dataset_test, batch_size=1, shuffle=True)
    img_size = rice_dataset_test.__getitem__(0)[0].shape[1]
    num_classes = len(rice_dataset_test.classes)

    model = VisionPromptCLIP(backbone=backbone, config=config, prompt_config=prompt_config, img_size=img_size, num_classes=num_classes)
    model = model.to(args.device)

    # TODO: encapsulate into trainer
    model.train()
    predicted = []
    labels = []
    optimizer = torch.optim.Adam(model.parameters(), lr=5e-3)
    loss_fn = torch.nn.CrossEntropyLoss()

    for img, label, idx in tqdm(train_loader):
        image_features = model.forward(img)
        # check how this improve linear probe accuracy
        with autocast():
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)

            logit_scale = backbone.logit_scale.exp()
            logits = logit_scale * (100.0 * image_features @ text_features.T)
            loss = loss_fn(logits, label.to(args.device))

            # update weights set torch autograd 
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # find the highest logit for each image in the batch
        _, indices = logits.max(dim=-1)
        predicted.append(indices.cpu().numpy())
        labels.append(label.cpu().numpy())

        # print loss and accuracy in each batch inside tqdm
        tqdm.write(f"Loss = {loss.item()}")
        tqdm.write(f"Accuracy = {(indices == label.to(args.device)).float().mean().item()}")
    
    # calculate accuracy
    predicted = np.concatenate(predicted)
    labels = np.concatenate(labels)

    accuracy = (predicted == labels).mean()
    print(f"Train Accuracy = {accuracy}")


if __name__ == '__main__':
    main()
